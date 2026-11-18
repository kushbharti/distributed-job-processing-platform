from app.core.config import settings
from app.services.reliability import backoff_seconds


def test_backoff_grows_exponentially_with_bounded_jitter(monkeypatch):
    monkeypatch.setattr(settings, "JOB_RETRY_BASE_SECONDS", 5)
    monkeypatch.setattr(settings, "JOB_RETRY_MAX_SECONDS", 300)
    for attempt, base in [(0, 5), (1, 10), (2, 20), (3, 40)]:
        for _ in range(20):
            assert base <= backoff_seconds(attempt) <= base * 1.25


def test_backoff_is_capped(monkeypatch):
    monkeypatch.setattr(settings, "JOB_RETRY_BASE_SECONDS", 5)
    monkeypatch.setattr(settings, "JOB_RETRY_MAX_SECONDS", 300)
    assert 300 <= backoff_seconds(30) <= 300 * 1.25