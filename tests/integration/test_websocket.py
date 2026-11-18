import uuid

import pytest
from starlette.websockets import WebSocketDisconnect

from app.api.v1.endpoints import websocket as ws_endpoint
from app.websocket.events import publish_job_event
from app.websocket.manager import limiter


def url(job_id) -> str:
    return f"/api/v1/ws/jobs/{job_id}"


def token_of(headers: dict) -> str:
    return headers["Authorization"].split(" ", 1)[1]


def expect_close(ws, code: int):
    with pytest.raises(WebSocketDisconnect) as excinfo:
        ws.receive_json()
    assert excinfo.value.code == code


def test_snapshot_then_live_events_then_clean_close(client, auth_headers, queued_job):
    with client.websocket_connect(url(queued_job["id"])) as ws:
        ws.send_json({"type": "auth", "token": token_of(auth_headers)})

        snapshot = ws.receive_json()
        assert snapshot["type"] == "snapshot" and snapshot["data"]["status"] == "QUEUED"

        publish_job_event(queued_job["id"], "PROCESSING", 40, "Extracting text")
        event = ws.receive_json()
        assert event["type"] == "event"
        assert event["data"]["status"] == "PROCESSING"
        assert event["data"]["progress"] == 40
        assert event["data"]["current_stage"] == "Extracting text"

        publish_job_event(queued_job["id"], "COMPLETED", 100, "Completed")
        assert ws.receive_json()["data"]["status"] == "COMPLETED"
        expect_close(ws, 1000)


def test_already_finished_job_sends_snapshot_and_closes(client, auth_headers, queued_job, run_sql):
    run_sql("UPDATE jobs SET status = 'COMPLETED', progress = 100 WHERE id = CAST(:id AS uuid)", id=queued_job["id"])
    with client.websocket_connect(url(queued_job["id"])) as ws:
        ws.send_json({"type": "auth", "token": token_of(auth_headers)})
        assert ws.receive_json()["data"]["status"] == "COMPLETED"
        expect_close(ws, 1000)


def test_missing_auth_message_times_out(client, queued_job, monkeypatch):
    monkeypatch.setattr(ws_endpoint, "AUTH_TIMEOUT_SECONDS", 0.3)
    with client.websocket_connect(url(queued_job["id"])) as ws:
        expect_close(ws, 4401)


def test_invalid_token_is_rejected(client, queued_job):
    with client.websocket_connect(url(queued_job["id"])) as ws:
        ws.send_json({"type": "auth", "token": "garbage"})
        expect_close(ws, 4401)


def test_revoked_token_is_rejected(client, auth_headers, queued_job):
    client.post("/api/v1/auth/logout", headers=auth_headers)
    with client.websocket_connect(url(queued_job["id"])) as ws:
        ws.send_json({"type": "auth", "token": token_of(auth_headers)})
        expect_close(ws, 4401)


def test_other_users_job_is_not_found(client, other_headers, queued_job):
    with client.websocket_connect(url(queued_job["id"])) as ws:
        ws.send_json({"type": "auth", "token": token_of(other_headers)})
        expect_close(ws, 4404)


def test_unknown_job_is_not_found(client, auth_headers):
    with client.websocket_connect(url(uuid.uuid4())) as ws:
        ws.send_json({"type": "auth", "token": token_of(auth_headers)})
        expect_close(ws, 4404)


def test_connection_limit_per_user(client, auth_headers, queued_job, monkeypatch):
    monkeypatch.setattr(limiter, "max_per_user", 1)
    with client.websocket_connect(url(queued_job["id"])) as first:
        first.send_json({"type": "auth", "token": token_of(auth_headers)})
        assert first.receive_json()["type"] == "snapshot"  # the first connection holds the only slot

        with client.websocket_connect(url(queued_job["id"])) as second:
            second.send_json({"type": "auth", "token": token_of(auth_headers)})
            expect_close(second, 1008)