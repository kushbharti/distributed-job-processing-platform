import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.dependencies import DbSession
from app.models.user import User
from app.services import auth_service, token_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")


def _credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_token_payload(token: Annotated[str, Depends(oauth2_scheme)]) -> dict:
    """Verify signature and expiry, then make sure the token was not revoked."""
    try:
        payload = decode_access_token(token)
    except jwt.InvalidTokenError:
        raise _credentials_error() from None

    try:
        revoked = token_service.is_revoked(payload["jti"])
    except RedisError:
      
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Authentication service temporarily unavailable",
        ) from None
    if revoked:
        raise _credentials_error()
    return payload


TokenPayload = Annotated[dict, Depends(get_token_payload)]


def get_current_user(db: DbSession, payload: TokenPayload) -> User:
    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError:
        raise _credentials_error() from None

    user = auth_service.get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise _credentials_error()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]