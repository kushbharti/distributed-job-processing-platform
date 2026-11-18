from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import settings

API = "/api/v1/auth"


def test_register_returns_user_without_password(client):
    response = client.post(f"{API}/register", json={"email": "A@Example.com", "password": "StrongPass123"})
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "a@example.com"  # normalised to lowercase
    assert "password" not in body and "hashed_password" not in body


def test_duplicate_email_is_rejected_case_insensitively(client):
    client.post(f"{API}/register", json={"email": "dup@example.com", "password": "StrongPass123"})
    response = client.post(f"{API}/register", json={"email": "DUP@example.com", "password": "StrongPass123"})
    assert response.status_code == 409


def test_register_validates_input(client):
    assert client.post(f"{API}/register", json={"email": "a@example.com", "password": "short"}).status_code == 422
    assert client.post(f"{API}/register", json={"email": "not-an-email", "password": "StrongPass123"}).status_code == 422


def test_password_is_stored_hashed(client, run_sql):
    client.post(f"{API}/register", json={"email": "h@example.com", "password": "StrongPass123"})
    stored = run_sql("SELECT hashed_password FROM users")[0][0]
    assert stored.startswith("$argon2") and "StrongPass123" not in stored


def test_login_success(client):
    client.post(f"{API}/register", json={"email": "l@example.com", "password": "StrongPass123"})
    response = client.post(f"{API}/login", data={"username": "l@example.com", "password": "StrongPass123"})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer" and body["access_token"]
    assert body["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def test_wrong_password_and_unknown_email_give_the_same_error(client):
    client.post(f"{API}/register", json={"email": "w@example.com", "password": "StrongPass123"})
    wrong = client.post(f"{API}/login", data={"username": "w@example.com", "password": "nope-nope-nope"})
    unknown = client.post(f"{API}/login", data={"username": "ghost@example.com", "password": "nope-nope-nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()  # no hint about which emails exist


def test_me_requires_a_token(client):
    assert client.get(f"{API}/me").status_code == 401


def test_me_returns_the_current_user(client, auth_headers):
    response = client.get(f"{API}/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_garbage_token_is_rejected(client):
    assert client.get(f"{API}/me", headers={"Authorization": "Bearer not.a.token"}).status_code == 401


def test_expired_token_is_rejected(client, auth_headers):
    user_id = client.get(f"{API}/me", headers=auth_headers).json()["id"]
    expired = jwt.encode(
        {"sub": user_id, "jti": "old", "exp": datetime.now(UTC) - timedelta(minutes=1)},
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    assert client.get(f"{API}/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_logout_revokes_only_that_token(client, auth_headers):
    second_login = client.post(f"{API}/login", data={"username": "user@example.com", "password": "StrongPass123"})
    other_token = {"Authorization": f"Bearer {second_login.json()['access_token']}"}

    assert client.post(f"{API}/logout", headers=auth_headers).status_code == 204
    assert client.get(f"{API}/me", headers=auth_headers).status_code == 401
    assert client.get(f"{API}/me", headers=other_token).status_code == 200  # other session unaffected