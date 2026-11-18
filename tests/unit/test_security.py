import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_is_hashed_with_argon2_and_verifies():
    hashed = hash_password("CorrectHorse1")
    assert hashed != "CorrectHorse1"
    assert hashed.startswith("$argon2")
    assert verify_password("CorrectHorse1", hashed)
    assert not verify_password("wrong-password", hashed)


def test_same_password_produces_different_hashes():
    assert hash_password("SamePassword1") != hash_password("SamePassword1")


def test_access_token_round_trip():
    user_id = uuid.uuid4()
    payload = decode_access_token(create_access_token(user_id))
    assert payload["sub"] == str(user_id)
    assert payload["jti"]


def test_every_token_has_a_unique_id():
    user_id = uuid.uuid4()
    first = decode_access_token(create_access_token(user_id))
    second = decode_access_token(create_access_token(user_id))
    assert first["jti"] != second["jti"]


def test_tampered_token_is_rejected():
    header, payload, signature = create_access_token(uuid.uuid4()).split(".")
    signature = ("A" if signature[0] != "A" else "B") + signature[1:]
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(f"{header}.{payload}.{signature}")


def test_expired_token_is_rejected():
    token = jwt.encode(
        {"sub": "x", "jti": "j", "exp": datetime.now(UTC) - timedelta(minutes=1)},
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_token_missing_required_claims_is_rejected():
    token = jwt.encode({"sub": "x"}, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token)


def test_token_signed_with_another_key_is_rejected():
    forged = jwt.encode(
        {"sub": "x", "jti": "j", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        "some-other-secret-key-that-is-also-long-enough",
        algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(forged)