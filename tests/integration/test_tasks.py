from app.core.config import settings
from app.services import outbox_service
from app.services.recovery_service import recover_stale_jobs
from app.tasks import document_tasks
from app.tasks.document_tasks import process_document

API = "/api/v1/jobs"


def test_worker_completes_a_job_and_stores_results(client, auth_headers, queued_job, fetch_job):
    result = process_document.apply(args=[queued_job["id"]])
    assert result.result == {"status": "COMPLETED"}

    job = fetch_job(queued_job["id"])
    assert job.status == "COMPLETED" and job.progress == 100
    assert job.started_at and job.completed_at

    body = client.get(f"{API}/{queued_job['id']}/result", headers=auth_headers).json()
    assert body["stats"]["pages"] == 2 and body["summary"] and body["keywords"]

    report = client.get(f"{API}/{queued_job['id']}/result/report", headers=auth_headers)
    assert report.status_code == 200 and report.content.startswith(b"%PDF")
    text = client.get(f"{API}/{queued_job['id']}/result/text", headers=auth_headers)
    assert text.status_code == 200 and "Workers process queued jobs" in text.text


def test_running_the_same_task_twice_is_idempotent(queued_job, fetch_job, run_sql):
    process_document.apply(args=[queued_job["id"]])
    second = process_document.apply(args=[queued_job["id"]])  # duplicate delivery
    assert second.result == {"skipped": True}
    assert fetch_job(queued_job["id"]).status == "COMPLETED"
    assert run_sql("SELECT count(*) FROM job_results")[0][0] == 1


def test_unreadable_pdf_fails_permanently_without_retries(client, auth_headers, upload_pdf, make_pdf, fetch_job):
    blank = upload_pdf(auth_headers, content=make_pdf(pages=1, text=None)).json()
    job = client.post(API, headers=auth_headers, json={"document_id": blank["id"]}).json()

    process_document.apply(args=[job["id"]])
    finished = fetch_job(job["id"])
    assert finished.status == "FAILED"
    assert "No extractable text" in finished.error_message
    assert finished.retry_count == 0  # permanent errors are not retried


def test_temporary_error_is_retried_and_then_succeeds(queued_job, fetch_job, monkeypatch):
    real_pipeline = document_tasks.run_pipeline
    calls = {"count": 0}

    def flaky(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError("disk hiccup")
        return real_pipeline(**kwargs)

    monkeypatch.setattr(document_tasks, "run_pipeline", flaky)
    process_document.apply(args=[queued_job["id"]])

    job = fetch_job(queued_job["id"])
    assert job.status == "COMPLETED"
    assert job.retry_count == 1 and calls["count"] == 2


def test_retries_are_bounded(queued_job, fetch_job, monkeypatch):
    monkeypatch.setattr(settings, "JOB_MAX_RETRIES", 2)
    calls = {"count": 0}

    def always_fails(**kwargs):
        calls["count"] += 1
        raise OSError("still broken")

    monkeypatch.setattr(document_tasks, "run_pipeline", always_fails)
    process_document.apply(args=[queued_job["id"]])

    job = fetch_job(queued_job["id"])
    assert job.status == "FAILED"
    assert job.retry_count == 2 and calls["count"] == 3  # first attempt + 2 retries
    assert "2 retries" in job.error_message


def test_unexpected_errors_fail_the_job_without_leaking_details(queued_job, fetch_job, monkeypatch):
    def buggy(**kwargs):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(document_tasks, "run_pipeline", buggy)
    result = process_document.apply(args=[queued_job["id"]])

    assert result.failed()  # the traceback still reaches the worker log
    job = fetch_job(queued_job["id"])
    assert job.status == "FAILED"
    assert job.error_message == "Unexpected processing error"
    assert "secret" not in job.error_message


def test_job_cancelled_before_the_worker_starts_is_skipped(client, auth_headers, queued_job, fetch_job):
    client.post(f"{API}/{queued_job['id']}/cancel", headers=auth_headers)
    assert process_document.apply(args=[queued_job["id"]]).result == {"skipped": True}
    assert fetch_job(queued_job["id"]).status == "CANCELLED"


def test_job_cancelled_while_running_stops_at_the_next_progress_update(queued_job, fetch_job, run_sql, monkeypatch):
    def cancelled_midway(**kwargs):
        run_sql("UPDATE jobs SET status = 'CANCELLED' WHERE id = CAST(:id AS uuid)", id=queued_job["id"])
        kwargs["on_progress"]("Extracting text", 40)  # the worker notices here

    monkeypatch.setattr(document_tasks, "run_pipeline", cancelled_midway)
    assert process_document.apply(args=[queued_job["id"]]).result == {"cancelled": True}
    assert fetch_job(queued_job["id"]).status == "CANCELLED"


def test_stale_processing_job_is_recovered_and_completes(queued_job, fetch_job, run_sql, sent_tasks):
    run_sql(
        "UPDATE jobs SET status = 'PROCESSING', heartbeat_at = now() - interval '1 hour' "
        "WHERE id = CAST(:id AS uuid)",
        id=queued_job["id"],
    )
    changes = recover_stale_jobs()
    assert [(str(c[0]), c[1]) for c in changes] == [(queued_job["id"], "RETRYING")]
    assert fetch_job(queued_job["id"]).retry_count == 1

    assert outbox_service.dispatch_pending() == 1  # re-queued through the outbox
    assert len(sent_tasks) == 2

    process_document.apply(args=[queued_job["id"]])  # a healthy worker picks it up
    job = fetch_job(queued_job["id"])
    assert job.status == "COMPLETED" and job.retry_count == 1


def test_stale_job_fails_when_its_retry_budget_is_used_up(queued_job, fetch_job, run_sql):
    run_sql(
        "UPDATE jobs SET status = 'PROCESSING', retry_count = :n, heartbeat_at = now() - interval '1 hour' "
        "WHERE id = CAST(:id AS uuid)",
        id=queued_job["id"],
        n=settings.JOB_MAX_RETRIES,
    )
    recover_stale_jobs()
    job = fetch_job(queued_job["id"])
    assert job.status == "FAILED" and "retry limit" in job.error_message


def test_jobs_with_a_fresh_heartbeat_are_left_alone(queued_job, fetch_job, run_sql):
    run_sql(
        "UPDATE jobs SET status = 'PROCESSING', heartbeat_at = now() WHERE id = CAST(:id AS uuid)",
        id=queued_job["id"],
    )
    assert recover_stale_jobs() == []
    assert fetch_job(queued_job["id"]).status == "PROCESSING"