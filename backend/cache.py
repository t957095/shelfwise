"""ShelfWise Cache Layer.

In-memory LRU + TTL cache for UPC lookups and HTTP responses.
Uses a simple dict with expiration timestamps.
"""

import threading
import time
from collections import OrderedDict
from typing import Any, Dict, Optional

DEFAULT_TTL = 300  # 5 minutes
DEFAULT_MAX_SIZE = 1000


class TTLCache:
    """Thread-safe LRU cache with TTL expiration."""

    def __init__(self, max_size: int = DEFAULT_MAX_SIZE, ttl: float = DEFAULT_TTL):
        self.max_size = max_size
        self.ttl = ttl
        self._data: OrderedDict[str, tuple] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._data:
                return None
            value, expires = self._data[key]
            if time.time() > expires:
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        with self._lock:
            expires = time.time() + (ttl or self.ttl)
            self._data[key] = (value, expires)
            self._data.move_to_end(key)
            if len(self._data) > self.max_size:
                self._data.popitem(last=False)

    def delete(self, key: str):
        with self._lock:
            self._data.pop(key, None)

    def clear(self):
        with self._lock:
            self._data.clear()

    def stats(self) -> Dict[str, int]:
        with self._lock:
            now = time.time()
            valid = sum(1 for _, expires in self._data.values() if expires > now)
            return {"size": len(self._data), "valid": valid, "expired": len(self._data) - valid}


# Global cache instances
upc_cache = TTLCache(max_size=2000, ttl=600)
http_cache = TTLCache(max_size=500, ttl=120)
