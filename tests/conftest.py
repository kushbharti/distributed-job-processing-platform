"""Shared test setup.

SAFETY: the environment is redirected to dedicated test resources BEFORE the app is imported,
so the application (and Alembic) can only ever see the test database and test Redis DBs.
"""

import os
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
from decouple import config as env

ROOT = Path(__file__).resolve().parents[1]


def _with_path(url: str, path: str) -> str:
    return urlunsplit(urlsplit(url)._replace(path=path))


TEST_DATABASE_URL = env(
    "TEST_DATABASE_URL", default=_with_path(env("DATABASE_URL"), "/job_platform_test")
)
TEST_DB_NAME = urlsplit(TEST_DATABASE_URL).path.lstrip("/")
if not TEST_DB_NAME.endswith("_test"):
    raise RuntimeError(f"Refusing to run tests against database '{TEST_DB_NAME}': name must end with _test")

_redis_url = env("REDIS_URL")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["REDIS_URL"] = _with_path(_redis_url, "/15")
os.environ["CELERY_BROKER_URL"] = _with_path(_redis_url, "/14")
os.environ["CELERY_RESULT_BACKEND"] = _with_path(_redis_url, "/13")
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-hs256-signing"
os.environ["APP_ENV"] = "test"
os.environ["DEV_STAGE_DELAY_SECONDS"] = "0"

SENTENCES = (
    "Workers process queued jobs in the background. "
    "The API places each job on a queue and returns immediately. "
    "Several workers can consume the same queue in parallel. "
    "Reliable workers retry temporary failures with exponential backoff. "
    "A dashboard shows the status of every job for the user. "
    "Completed jobs store a summary and a generated report."
)


def _ensure_database() -> None:
    import psycopg
    from psycopg import sql

    admin_url = _with_path(TEST_DATABASE_URL, "/postgres").replace(
        "postgresql+psycopg://", "postgresql://", 1
    )
    with psycopg.connect(admin_url, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB_NAME,)
        ).fetchone()
        if not exists:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEST_DB_NAME)))


@pytest.fixture(scope="session", autouse=True)
def _database():
    """Create the test database if needed and build the schema with the real migrations."""
    from alembic.config import Config

    from alembic import command

    _ensure_database()
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    command.upgrade(cfg, "head")
    yield
    from app.db.session import engine

    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_state(tmp_path, monkeypatch):
    """Every test starts with empty tables, an empty Redis DB and its own upload folder."""
    from sqlalchemy import text

    from app.core.config import settings
    from app.core.redis import redis_client
    from app.db.base import Base
    from app.db.session import engine

    assert settings.DATABASE_URL.endswith(TEST_DB_NAME), "app is not using the test database"
    assert settings.REDIS_URL.endswith("/15"), "app is not using the test Redis DB"

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    redis_client.flushdb()
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    yield


# ---------------------------------------------------------------------------
# Helpers exposed as fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def make_pdf():
    import pymupdf

    def _make(pages: int = 2, text: str | None = SENTENCES) -> bytes:
        doc = pymupdf.open()
        for _ in range(pages):
            page = doc.new_page()
            if text:
                page.insert_textbox(pymupdf.Rect(50, 50, 545, 790), text, fontsize=11)
        data = doc.tobytes()
        doc.close()
        return data

    return _make


@pytest.fixture
def run_sql():
    from sqlalchemy import text

    from app.db.session import engine

    def _run(statement: str, **params):
        with engine.begin() as conn:
            result = conn.execute(text(statement), params)
            return result.all() if result.returns_rows else None

    return _run


@pytest.fixture
def fetch_job():
    from app.db.session import SessionLocal
    from app.models.job import Job

    def _fetch(job_id) -> Job | None:
        with SessionLocal() as db:  # a fresh session, so we never read stale cached rows
            return db.get(Job, uuid.UUID(str(job_id)))

    return _fetch


@pytest.fixture
def sent_tasks(monkeypatch):
    """Replace Celery publishing with a recorder, so API tests never need a worker."""
    from app.tasks.celery_app import celery_app

    sent: list[dict] = []

    def fake_send_task(name, args=None, kwargs=None, task_id=None, **options):
        sent.append({"name": name, "args": args, "task_id": task_id})

    monkeypatch.setattr(celery_app, "send_task", fake_send_task)
    return sent


@pytest.fixture
def client(sent_tasks):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def register_and_login(client, email: str, password: str = "StrongPass123") -> dict:
    response = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    response = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def auth_headers(client) -> dict:
    return register_and_login(client, "user@example.com")


@pytest.fixture
def other_headers(client) -> dict:
    return register_and_login(client, "other@example.com")


@pytest.fixture
def upload_pdf(client, make_pdf):
    def _upload(headers, content=None, filename="sample.pdf", content_type="application/pdf"):
        content = make_pdf() if content is None else content
        return client.post(
            "/api/v1/documents/upload",
            headers=headers,
            files={"file": (filename, content, content_type)},
        )

    return _upload


@pytest.fixture
def document(auth_headers, upload_pdf) -> dict:
    response = upload_pdf(auth_headers)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def queued_job(client, auth_headers, document) -> dict:
    response = client.post(
        "/api/v1/jobs", headers=auth_headers, json={"document_id": document["id"]}
    )
    assert response.status_code == 202, response.text
    return response.json()