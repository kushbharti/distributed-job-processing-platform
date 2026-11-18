import uuid

from app.services import outbox_service
from app.tasks.celery_app import celery_app

API = "/api/v1/jobs"


def create(client, headers, document_id):
    return client.post(API, headers=headers, json={"document_id": document_id})


def test_create_job_is_queued_and_published(client, auth_headers, document, sent_tasks):
    response = create(client, auth_headers, document["id"])
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "QUEUED" and body["progress"] == 0
    assert sent_tasks == [
        {"name": "jobs.process_document", "args": [body["id"]], "task_id": body["id"]}
    ]


def test_cannot_create_job_for_someone_elses_document(client, other_headers, document):
    assert create(client, other_headers, document["id"]).status_code == 404


def test_only_one_active_job_per_document(client, auth_headers, document, queued_job):
    assert create(client, auth_headers, document["id"]).status_code == 409


def test_new_job_is_allowed_after_the_previous_one_finished(client, auth_headers, document, queued_job, run_sql):
    run_sql("UPDATE jobs SET status = 'COMPLETED' WHERE id = CAST(:id AS uuid)", id=queued_job["id"])
    assert create(client, auth_headers, document["id"]).status_code == 202


def test_job_survives_a_broker_outage_and_is_dispatched_later(
    client, auth_headers, document, sent_tasks, monkeypatch, run_sql
):
    working_send = celery_app.send_task

    def broker_down(*args, **kwargs):
        raise ConnectionError("broker down")

    monkeypatch.setattr(celery_app, "send_task", broker_down)
    response = create(client, auth_headers, document["id"])
    assert response.status_code == 202
    assert response.json()["status"] == "PENDING"  # accepted, waiting in the outbox
    attempts, sent_at = run_sql("SELECT attempts, sent_at FROM outbox_events")[0]
    assert attempts == 1 and sent_at is None

    monkeypatch.setattr(celery_app, "send_task", working_send)  # broker is back
    assert outbox_service.dispatch_pending() == 1
    assert client.get(f"{API}/{response.json()['id']}", headers=auth_headers).json()["status"] == "QUEUED"
    assert len(sent_tasks) == 1


def test_jobs_are_scoped_to_their_owner(client, auth_headers, other_headers, queued_job):
    assert client.get(f"{API}/{queued_job['id']}", headers=other_headers).status_code == 404
    assert client.get(f"{API}/{queued_job['id']}/result", headers=other_headers).status_code == 404
    assert client.post(f"{API}/{queued_job['id']}/cancel", headers=other_headers).status_code == 404
    assert client.get(API, headers=other_headers).json()["total"] == 0


def test_list_filters_by_status(client, auth_headers, queued_job, run_sql):
    assert client.get(API, headers=auth_headers, params={"status": "QUEUED"}).json()["total"] == 1
    assert client.get(API, headers=auth_headers, params={"status": "COMPLETED"}).json()["total"] == 0
    assert client.get(API, headers=auth_headers, params={"status": "BOGUS"}).status_code == 422


def test_cancel_a_queued_job(client, auth_headers, queued_job):
    response = client.post(f"{API}/{queued_job['id']}/cancel", headers=auth_headers)
    assert response.status_code == 200 and response.json()["status"] == "CANCELLED"


def test_cannot_cancel_a_finished_job(client, auth_headers, queued_job, run_sql):
    run_sql("UPDATE jobs SET status = 'COMPLETED' WHERE id = CAST(:id AS uuid)", id=queued_job["id"])
    assert client.post(f"{API}/{queued_job['id']}/cancel", headers=auth_headers).status_code == 409


def test_result_is_unavailable_until_completed(client, auth_headers, queued_job):
    assert client.get(f"{API}/{queued_job['id']}/result", headers=auth_headers).status_code == 409


def test_retry_a_failed_job(client, auth_headers, queued_job, run_sql, sent_tasks):
    run_sql(
        "UPDATE jobs SET status = 'FAILED', error_message = 'boom', retry_count = 3 WHERE id = CAST(:id AS uuid)",
        id=queued_job["id"],
    )
    response = client.post(f"{API}/{queued_job['id']}/retry", headers=auth_headers)
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "QUEUED" and body["error_message"] is None and body["retry_count"] == 0
    assert len(sent_tasks) == 2  # the original dispatch plus the retry


def test_retry_rejects_jobs_that_are_not_failed(client, auth_headers, queued_job):
    assert client.post(f"{API}/{queued_job['id']}/retry", headers=auth_headers).status_code == 409


def test_retry_conflicts_with_another_active_job(client, auth_headers, document, queued_job, run_sql):
    run_sql("UPDATE jobs SET status = 'FAILED' WHERE id = CAST(:id AS uuid)", id=queued_job["id"])
    assert create(client, auth_headers, document["id"]).status_code == 202  # a new active job
    assert client.post(f"{API}/{queued_job['id']}/retry", headers=auth_headers).status_code == 409


def test_document_with_an_active_job_cannot_be_deleted(client, auth_headers, document, queued_job):
    url = f"/api/v1/documents/{document['id']}"
    assert client.delete(url, headers=auth_headers).status_code == 409
    client.post(f"{API}/{queued_job['id']}/cancel", headers=auth_headers)
    assert client.delete(url, headers=auth_headers).status_code == 204
    assert client.get(f"{API}/{queued_job['id']}", headers=auth_headers).status_code == 404  # cascaded


def test_unknown_job_is_404(client, auth_headers):
    assert client.get(f"{API}/{uuid.uuid4()}", headers=auth_headers).status_code == 404