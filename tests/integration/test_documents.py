import uuid

from app.core.config import settings

API = "/api/v1/documents"


def stored_pdfs():
    return list(settings.upload_path.rglob("*.pdf"))


def test_upload_valid_pdf(auth_headers, upload_pdf):
    response = upload_pdf(auth_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["page_count"] == 2
    assert body["filename"] == "sample.pdf"
    assert "file_path" not in body and "stored_filename" not in body  # internals are not exposed
    assert len(stored_pdfs()) == 1


def test_rejects_wrong_extension(auth_headers, upload_pdf):
    assert upload_pdf(auth_headers, filename="notes.txt").status_code == 400
    assert stored_pdfs() == []


def test_rejects_wrong_content_type(auth_headers, upload_pdf):
    assert upload_pdf(auth_headers, content_type="text/plain").status_code == 400


def test_rejects_file_without_pdf_signature(auth_headers, upload_pdf):
    response = upload_pdf(auth_headers, content=b"just some text", filename="fake.pdf")
    assert response.status_code == 400
    assert "not a valid PDF" in response.json()["detail"]
    assert stored_pdfs() == []  # nothing left on disk


def test_rejects_corrupted_pdf_and_cleans_up(auth_headers, upload_pdf):
    response = upload_pdf(auth_headers, content=b"%PDF-1.4 garbage", filename="bad.pdf")
    assert response.status_code == 400
    assert stored_pdfs() == []


def test_rejects_oversized_file_and_cleans_up(auth_headers, upload_pdf, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    big = b"%PDF-1.4\n" + b"0" * (1024 * 1024 + 10)
    response = upload_pdf(auth_headers, content=big)
    assert response.status_code == 413
    assert stored_pdfs() == []


def test_upload_requires_authentication(upload_pdf):
    assert upload_pdf({}).status_code == 401


def test_list_is_paginated_and_scoped_to_owner(client, auth_headers, other_headers, upload_pdf):
    for _ in range(3):
        upload_pdf(auth_headers)
    upload_pdf(other_headers)

    page = client.get(API, headers=auth_headers, params={"limit": 2}).json()
    assert page["total"] == 3 and len(page["items"]) == 2 and page["limit"] == 2
    assert client.get(API, headers=other_headers).json()["total"] == 1


def test_other_users_cannot_read_or_delete_a_document(client, auth_headers, other_headers, document):
    url = f"{API}/{document['id']}"
    assert client.get(url, headers=other_headers).status_code == 404
    assert client.delete(url, headers=other_headers).status_code == 404
    assert client.get(url, headers=auth_headers).status_code == 200  # still there for the owner


def test_delete_removes_row_and_file(client, auth_headers, document):
    url = f"{API}/{document['id']}"
    assert client.delete(url, headers=auth_headers).status_code == 204
    assert client.get(url, headers=auth_headers).status_code == 404
    assert stored_pdfs() == []


def test_malformed_id_is_a_validation_error(client, auth_headers):
    assert client.get(f"{API}/not-a-uuid", headers=auth_headers).status_code == 422
    assert client.get(f"{API}/{uuid.uuid4()}", headers=auth_headers).status_code == 404
    
def test_cleanup_failure_does_not_mask_the_validation_error(auth_headers, upload_pdf, monkeypatch):
    from pathlib import Path

    def locked(self, missing_ok=False):
        raise PermissionError("file is locked")

    monkeypatch.setattr(Path, "unlink", locked)
    response = upload_pdf(auth_headers, content=b"%PDF-1.4 garbage", filename="bad.pdf")
    assert response.status_code == 400  
    
def test_document_list_includes_the_latest_job(client, auth_headers, document, queued_job):
    item = client.get(API, headers=auth_headers).json()["items"][0]
    assert item["latest_job"] == {"id": queued_job["id"], "status": "QUEUED"}


def test_document_without_jobs_has_no_latest_job(client, auth_headers, document):
    assert client.get(f"{API}/{document['id']}", headers=auth_headers).json()["latest_job"] is None