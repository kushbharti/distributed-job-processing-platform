import time

from app.core.redis import redis_client

PREFIX = "denylist:jti:"


def revoke_token(jti: str, exp: int) -> None:
    """Block this token until it would have expired anyway."""
    ttl = max(int(exp - time.time()), 1)
    redis_client.set(f"{PREFIX}{jti}", "1", ex=ttl)


def is_revoked(jti: str) -> bool:
    return redis_client.exists(f"{PREFIX}{jti}") == 1