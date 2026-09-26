"""
Pembatas percobaan gagal (in-memory, sliding window) — dipakai login.

Catatan:
- Disimpan di memori proses: hitungan hilang saat backend restart, dan
  hanya benar untuk satu proses uvicorn (tanpa --workers > 1).
- Kunci IP diambil dari request.client.host. Kalau backend nanti dipasang
  di belakang reverse proxy, semua request terlihat dari IP proxy —
  sesuaikan dulu (lihat roadmap Fase 9 poin 19).
"""
import math
import threading
import time
from collections import deque


class FailedAttemptLimiter:
    """Blokir sebuah kunci setelah `max_failures` kegagalan dalam `window_seconds`."""

    def __init__(self, max_failures: int, window_seconds: float):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._failures: dict[str, deque] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque | None:
        q = self._failures.get(key)
        if q is None:
            return None
        while q and q[0] <= now - self.window_seconds:
            q.popleft()
        if not q:
            del self._failures[key]
            return None
        return q

    def retry_after(self, key: str) -> int:
        """Detik sampai kunci boleh mencoba lagi; 0 = boleh sekarang."""
        with self._lock:
            now = time.monotonic()
            q = self._prune(key, now)
            if q is None or len(q) < self.max_failures:
                return 0
            return max(1, math.ceil(q[0] + self.window_seconds - now))

    def record_failure(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            # Buang kunci yang sudah kedaluwarsa agar dict tidak tumbuh terus
            for k in list(self._failures):
                self._prune(k, now)
            self._failures.setdefault(key, deque()).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
