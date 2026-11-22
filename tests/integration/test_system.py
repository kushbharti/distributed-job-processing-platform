from redis.exceptions import RedisError

from app.core.redis import redis_client


def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_reports_all_dependencies(client):
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "ok", "redis": "ok"}


def test_ready_returns_503_when_redis_is_down(client, monkeypatch):
    def boom():
        raise RedisError("down")

    monkeypatch.setattr(redis_client, "ping", boom)
    response = client.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json()["detail"]["checks"]["redis"] == "unavailable"
    assert response.json()["detail"]["checks"]["database"] == "ok"

def test_index_page_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'id="app"' in response.text


def test_javascript_modules_are_served_with_a_javascript_mime_type(client):
    response = client.get("/static/js/main.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]