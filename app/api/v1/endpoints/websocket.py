import asyncio
import contextlib
import json
import logging
import time
import uuid

import jwt
import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models.job import Job
from app.services import auth_service, job_service, token_service
from app.websocket.events import TERMINAL_STATUSES, channel_for, snapshot_from_job
from app.websocket.manager import limiter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

AUTH_TIMEOUT_SECONDS = 5.0

CLOSE_NORMAL = 1000
CLOSE_POLICY = 1008
CLOSE_INTERNAL = 1011
CLOSE_TRY_LATER = 1013
CLOSE_UNAUTHORIZED = 4401
CLOSE_NOT_FOUND = 4404


class WSAuthError(Exception):
    def __init__(self, code: int, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


def _authenticate(token: str, job_id: uuid.UUID) -> tuple[uuid.UUID, int]:
    """Blocking work (JWT, Redis denylist, database); run it in a thread pool."""
    try:
        payload = decode_access_token(token)
    except jwt.InvalidTokenError:
        raise WSAuthError(CLOSE_UNAUTHORIZED, "Invalid or expired token") from None

    try:
        revoked = token_service.is_revoked(payload["jti"])
    except RedisError:
        raise WSAuthError(CLOSE_TRY_LATER, "Service temporarily unavailable") from None
    if revoked:
        raise WSAuthError(CLOSE_UNAUTHORIZED, "Token revoked")

    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError:
        raise WSAuthError(CLOSE_UNAUTHORIZED, "Invalid token") from None

    with SessionLocal() as db:
        user = auth_service.get_user_by_id(db, user_id)
        if user is None or not user.is_active:
            raise WSAuthError(CLOSE_UNAUTHORIZED, "Invalid token")
        # Ownership check: another user's job is simply "not found".
        if job_service.get_job(db, user.id, job_id) is None:
            raise WSAuthError(CLOSE_NOT_FOUND, "Job not found")
    return user_id, int(payload["exp"])


def _load_snapshot(job_id: uuid.UUID) -> dict | None:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        return snapshot_from_job(job) if job is not None else None


async def _receive_token(websocket: WebSocket) -> str | None:
    try:
        message = await asyncio.wait_for(websocket.receive_json(), timeout=AUTH_TIMEOUT_SECONDS)
    except (asyncio.TimeoutError, ValueError, KeyError, TypeError):
        return None
    if (
        isinstance(message, dict)
        and message.get("type") == "auth"
        and isinstance(message.get("token"), str)
    ):
        return message["token"]
    return None


async def _forward_events(websocket: WebSocket, pubsub, expires_at: int) -> tuple[int, str]:
    """Send Redis events to the client until the job ends or the token expires."""
    while True:
        remaining = expires_at - time.time()
        if remaining <= 0:
            return CLOSE_UNAUTHORIZED, "Token expired"
        message = await pubsub.get_message(
            ignore_subscribe_messages=True, timeout=min(remaining, 1.0)
        )
        if message is None:
            continue
        data = json.loads(message["data"])
        await websocket.send_json({"type": "event", "data": data})
        if data["status"] in TERMINAL_STATUSES:
            return CLOSE_NORMAL, "Job finished"


async def _watch_client(websocket: WebSocket) -> None:
    """Return as soon as the client disconnects (anything it sends is ignored)."""
    while True:
        message = await websocket.receive()
        if message["type"] == "websocket.disconnect":
            return


async def _safe_close(websocket: WebSocket, code: int, reason: str) -> None:
    with contextlib.suppress(Exception):
        await websocket.close(code, reason)


@router.websocket("/ws/jobs/{job_id}")
async def job_updates(websocket: WebSocket, job_id: uuid.UUID) -> None:
    await websocket.accept()
    user_id: uuid.UUID | None = None
    acquired = False
    redis_conn = None
    pubsub = None
    try:
        # 1) Authenticate with the first message.
        token = await _receive_token(websocket)
        if token is None:
            await websocket.close(CLOSE_UNAUTHORIZED, "Authentication required")
            return
        try:
            user_id, expires_at = await run_in_threadpool(_authenticate, token, job_id)
        except WSAuthError as exc:
            await websocket.close(exc.code, exc.reason)
            return

        if not limiter.try_acquire(user_id):
            await websocket.close(CLOSE_POLICY, "Too many connections")
            return
        acquired = True

        # 2) Subscribe FIRST, then read the current state, so no event can fall in the gap.
        redis_conn = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = redis_conn.pubsub()
        await pubsub.subscribe(channel_for(job_id))
        await pubsub.get_message(timeout=2.0)  # wait for Redis to confirm the subscription

        snapshot = await run_in_threadpool(_load_snapshot, job_id)
        if snapshot is None:
            await websocket.close(CLOSE_NOT_FOUND, "Job not found")
            return
        await websocket.send_json({"type": "snapshot", "data": snapshot})
        if snapshot["status"] in TERMINAL_STATUSES:
            await websocket.close(CLOSE_NORMAL, "Job finished")
            return

        # 3) Forward events until the job ends, the token expires or the client leaves.
        pump = asyncio.create_task(_forward_events(websocket, pubsub, expires_at))
        watcher = asyncio.create_task(_watch_client(websocket))
        done, pending = await asyncio.wait({pump, watcher}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        if pump in done:
            code, reason = pump.result()
            await websocket.close(code, reason)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.warning("WebSocket error for job %s", job_id, exc_info=True)
        await _safe_close(websocket, CLOSE_INTERNAL, "Internal error")
    finally:
        with contextlib.suppress(Exception):
            if pubsub is not None:
                await pubsub.unsubscribe()
                await pubsub.aclose()
        with contextlib.suppress(Exception):
            if redis_conn is not None:
                await redis_conn.aclose()
        if acquired and user_id is not None:
            limiter.release(user_id)