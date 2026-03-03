"""
Intelligent Caching System (v3.3.0)

Provides caching for browser operations:
- Page content caching
- Parsed element caching
- LRU eviction policy
- TTL-based expiration
- Persistent cache option
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any, Generic, TypeVar
from datetime import datetime, timedelta
from collections import OrderedDict
from pathlib import Path
import hashlib
import json
import logging
import threading

logger = logging.getLogger(__name__)


T = TypeVar('T')


@dataclass
class CacheEntry(Generic[T]):
    """A single cache entry."""
    key: str
    value: T
    created_at: datetime = field(default_factory=datetime.now)
    accessed_at: datetime = field(default_factory=datetime.now)
    ttl_seconds: Optional[float] = None
    access_count: int = 0
    size_bytes: int = 0

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl_seconds is None:
            return False
        age = (datetime.now() - self.created_at).total_seconds()
        return age > self.ttl_seconds


@dataclass
class CacheConfig:
    """Configuration for the cache."""
    max_entries: int = 1000
    max_size_bytes: int = 100 * 1024 * 1024  # 100MB
    default_ttl_seconds: float = 300.0       # 5 minutes
    persist: bool = False
    persist_path: Optional[Path] = None


class LRUCache(Generic[T]):
    """LRU cache with TTL support."""

    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._lock = threading.Lock()
        self._current_size = 0

        # Statistics
        self._hits = 0
        self._misses = 0

        # Load persisted cache if available
        if self.config.persist and self.config.persist_path:
            self._load_from_disk()

    def get(self, key: str) -> Optional[T]:
        """Get a value from cache."""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]

            # Check expiration
            if entry.is_expired():
                self._remove_entry(key)
                self._misses += 1
                return None

            # Update access
            entry.accessed_at = datetime.now()
            entry.access_count += 1
            self._cache.move_to_end(key)

            self._hits += 1
            return entry.value

    def set(
        self,
        key: str,
        value: T,
        ttl_seconds: Optional[float] = None,
        size_bytes: int = 0
    ):
        """Set a value in cache."""
        with self._lock:
            # Remove existing entry if present
            if key in self._cache:
                self._remove_entry(key)

            # Evict if necessary
            while self._should_evict(size_bytes):
                self._evict_one()

            entry = CacheEntry(
                key=key,
                value=value,
                ttl_seconds=ttl_seconds or self.config.default_ttl_seconds,
                size_bytes=size_bytes
            )

            self._cache[key] = entry
            self._current_size += size_bytes

    def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        with self._lock:
            if key in self._cache:
                self._remove_entry(key)
                return True
            return False

    def clear(self):
        """Clear all entries."""
        with self._lock:
            self._cache.clear()
            self._current_size = 0

    def _remove_entry(self, key: str):
        """Remove an entry (internal, no lock)."""
        if key in self._cache:
            entry = self._cache.pop(key)
            self._current_size -= entry.size_bytes

    def _should_evict(self, new_size: int) -> bool:
        """Check if we need to evict entries."""
        if len(self._cache) >= self.config.max_entries:
            return True
        if self._current_size + new_size > self.config.max_size_bytes:
            return True
        return False

    def _evict_one(self):
        """Evict the least recently used entry."""
        if self._cache:
            # First, try to evict expired entries
            for key, entry in list(self._cache.items()):
                if entry.is_expired():
                    self._remove_entry(key)
                    return

            # Otherwise, evict LRU
            oldest_key = next(iter(self._cache))
            self._remove_entry(oldest_key)

    def cleanup_expired(self):
        """Remove all expired entries."""
        with self._lock:
            expired = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            for key in expired:
                self._remove_entry(key)

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0

        return {
            "entries": len(self._cache),
            "size_bytes": self._current_size,
            "max_entries": self.config.max_entries,
            "max_size_bytes": self.config.max_size_bytes,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate
        }

    def stats(self) -> Dict:
        """Alias for get_stats() for API compatibility."""
        return self.get_stats()

    def contains(self, key: str) -> bool:
        """Check if a key exists in the cache (and is not expired)."""
        with self._lock:
            if key not in self._cache:
                return False
            entry = self._cache[key]
            if entry.is_expired():
                self._remove_entry(key)
                return False
            return True

    def _save_to_disk(self):
        """Save cache to disk (for serializable values only)."""
        if not self.config.persist_path:
            return

        try:
            data = {
                key: {
                    "value": entry.value,
                    "created_at": entry.created_at.isoformat(),
                    "ttl_seconds": entry.ttl_seconds
                }
                for key, entry in self._cache.items()
                if not entry.is_expired()
            }
            self.config.persist_path.write_text(json.dumps(data))
        except (OSError, TypeError, ValueError) as e:
            logger.debug("Failed to save cache to disk: %s", e)

    def _load_from_disk(self):
        """Load cache from disk."""
        if not self.config.persist_path or not self.config.persist_path.exists():
            return

        try:
            data = json.loads(self.config.persist_path.read_text())
            for key, info in data.items():
                created = datetime.fromisoformat(info["created_at"])
                ttl = info.get("ttl_seconds")
                entry = CacheEntry(
                    key=key,
                    value=info["value"],
                    created_at=created,
                    ttl_seconds=ttl
                )
                if not entry.is_expired():
                    self._cache[key] = entry
        except (OSError, ValueError, KeyError) as e:
            logger.debug("Failed to load cache from disk: %s", e)


class PageCache:
    """Specialized cache for page content."""

    def __init__(self, max_pages: int = 100):
        self.config = CacheConfig(
            max_entries=max_pages,
            max_size_bytes=50 * 1024 * 1024,  # 50MB
            default_ttl_seconds=60.0  # 1 minute for pages
        )
        self._html_cache = LRUCache[str](self.config)
        self._parsed_cache = LRUCache[Dict](self.config)

    def cache_page(self, url: str, html: str, parsed: Dict = None):
        """Cache page content."""
        key = self._url_key(url)
        self._html_cache.set(key, html, size_bytes=len(html.encode()))

        if parsed:
            self._parsed_cache.set(key, parsed)

    def get_html(self, url: str) -> Optional[str]:
        """Get cached HTML for a URL."""
        return self._html_cache.get(self._url_key(url))

    def get_parsed(self, url: str) -> Optional[Dict]:
        """Get cached parsed content for a URL."""
        return self._parsed_cache.get(self._url_key(url))

    def invalidate(self, url: str):
        """Invalidate cache for a URL."""
        key = self._url_key(url)
        self._html_cache.delete(key)
        self._parsed_cache.delete(key)

    def _url_key(self, url: str) -> str:
        """Generate cache key from URL.

        Uses blake2b which is ~2x faster than MD5 for small inputs.
        Only 16 bytes needed for cache keys (no cryptographic security needed).
        """
        return hashlib.blake2b(url.encode(), digest_size=16).hexdigest()

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            "html_cache": self._html_cache.get_stats(),
            "parsed_cache": self._parsed_cache.get_stats()
        }


class ResultCache:
    """Cache for search/query results."""

    def __init__(self, max_queries: int = 500):
        self.config = CacheConfig(
            max_entries=max_queries,
            default_ttl_seconds=3600.0  # 1 hour for search results
        )
        self._cache = LRUCache[Dict](self.config)

    def cache_results(self, query: str, results: Dict, source: str = ""):
        """Cache search results."""
        key = self._query_key(query, source)
        self._cache.set(key, results)

    def get_results(self, query: str, source: str = "") -> Optional[Dict]:
        """Get cached results for a query."""
        return self._cache.get(self._query_key(query, source))

    def _query_key(self, query: str, source: str) -> str:
        """Generate cache key from query.

        Uses blake2b for faster hashing (no cryptographic security needed).
        """
        combined = f"{source}:{query.lower().strip()}"
        return hashlib.blake2b(combined.encode(), digest_size=16).hexdigest()

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        return self._cache.get_stats()


# Global cache instances
_page_cache: Optional[PageCache] = None
_result_cache: Optional[ResultCache] = None


def get_page_cache() -> PageCache:
    """Get the global page cache."""
    global _page_cache
    if _page_cache is None:
        _page_cache = PageCache()
    return _page_cache


def get_result_cache() -> ResultCache:
    """Get the global result cache."""
    global _result_cache
    if _result_cache is None:
        _result_cache = ResultCache()
    return _result_cache
