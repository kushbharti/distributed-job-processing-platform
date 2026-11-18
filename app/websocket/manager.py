import threading
import uuid
from collections import defaultdict


class ConnectionLimiter:
    """Caps concurrent WebSockets per user so one account cannot exhaust the server.

    In-process only: with several API processes, each enforces the cap separately.
    """

    def __init__(self, max_per_user: int = 5) -> None:
        self.max_per_user = max_per_user
        self._counts: dict[uuid.UUID, int] = defaultdict(int)
        self._lock = threading.Lock()

    def try_acquire(self, user_id: uuid.UUID) -> bool:
        with self._lock:
            if self._counts[user_id] >= self.max_per_user:
                return False
            self._counts[user_id] += 1
            return True

    def release(self, user_id: uuid.UUID) -> None:
        with self._lock:
            self._counts[user_id] = max(self._counts[user_id] - 1, 0)


limiter = ConnectionLimiter(max_per_user=5)