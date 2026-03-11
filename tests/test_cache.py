"""
Unit tests for blackreach/cache.py

Tests LRU cache implementation with TTL support.
"""

import pytest
import time
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from blackreach.cache import (
    CacheEntry,
    CacheConfig,
    LRUCache,
    PageCache,
    ResultCache,
    get_page_cache,
    get_result_cache,
)


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_entry_creation(self):
        """CacheEntry should store all fields correctly."""
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            ttl_seconds=60.0,
            size_bytes=100
        )
        assert entry.key == "test_key"
        assert entry.value == "test_value"
        assert entry.ttl_seconds == 60.0
        assert entry.size_bytes == 100
        assert entry.access_count == 0

    def test_entry_not_expired_no_ttl(self):
        """Entry without TTL should never expire."""
        entry = CacheEntry(
            key="test",
            value="value",
            ttl_seconds=None
        )
        assert entry.is_expired() is False

    def test_entry_not_expired_within_ttl(self):
        """Entry within TTL should not be expired."""
        entry = CacheEntry(
            key="test",
            value="value",
            ttl_seconds=60.0  # 60 seconds
        )
        assert entry.is_expired() is False

    def test_entry_defaults(self):
        """CacheEntry should have correct defaults."""
        entry = CacheEntry(key="key", value="value")
        assert entry.access_count == 0
        assert entry.size_bytes == 0
        assert entry.ttl_seconds is None


class TestCacheConfig:
    """Tests for CacheConfig dataclass."""

    def test_default_values(self):
        """CacheConfig has sensible defaults."""
        config = CacheConfig()
        assert config.max_entries == 1000
        assert config.max_size_bytes == 100 * 1024 * 1024  # 100MB
        assert config.default_ttl_seconds == 300.0  # 5 minutes
        assert config.persist is False
        assert config.persist_path is None

    def test_custom_values(self):
        """CacheConfig accepts custom values."""
        from pathlib import Path
        config = CacheConfig(
            max_entries=500,
            max_size_bytes=50 * 1024 * 1024,
            default_ttl_seconds=120.0,
            persist=True,
            persist_path=Path("/tmp/cache")
        )
        assert config.max_entries == 500
        assert config.max_size_bytes == 50 * 1024 * 1024
        assert config.default_ttl_seconds == 120.0
        assert config.persist is True


class TestLRUCache:
    """Tests for LRUCache class."""

    def test_init(self):
        """LRUCache initializes correctly."""
        cache = LRUCache()
        assert cache is not None

    def test_init_with_config(self):
        """LRUCache accepts custom config."""
        config = CacheConfig(max_entries=100)
        cache = LRUCache(config=config)
        assert cache.config.max_entries == 100

    def test_set_and_get(self):
        """Should store and retrieve values."""
        cache = LRUCache()
        cache.set("key1", "value1")
        result = cache.get("key1")
        assert result == "value1"

    def test_get_missing_key(self):
        """Should return None for missing keys."""
        cache = LRUCache()
        result = cache.get("nonexistent")
        assert result is None

    def test_delete(self):
        """Should delete entries."""
        cache = LRUCache()
        cache.set("key1", "value1")
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_clear(self):
        """Should clear all entries."""
        cache = LRUCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_lru_eviction(self):
        """Least recently used entries should be evicted."""
        config = CacheConfig(max_entries=2)
        cache = LRUCache(config=config)

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        # Access key1 to make it recently used
        cache.get("key1")

        # Add key3, should evict key2 (least recently used)
        cache.set("key3", "value3")

        assert cache.get("key1") is not None
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") is not None


class TestLRUCacheStatistics:
    """Tests for cache statistics."""

    def test_hit_count(self):
        """Should track cache hits."""
        cache = LRUCache()
        cache.set("key1", "value1")

        cache.get("key1")  # Hit
        cache.get("key1")  # Hit

        stats = cache.stats()
        assert stats["hits"] == 2

    def test_miss_count(self):
        """Should track cache misses."""
        cache = LRUCache()

        cache.get("nonexistent1")  # Miss
        cache.get("nonexistent2")  # Miss

        stats = cache.stats()
        assert stats["misses"] == 2

    def test_hit_rate(self):
        """Should calculate hit rate correctly."""
        cache = LRUCache()
        cache.set("key1", "value1")

        cache.get("key1")  # Hit
        cache.get("key1")  # Hit
        cache.get("nonexistent")  # Miss

        stats = cache.stats()
        # 2 hits, 1 miss = 2/3 hit rate
        assert 0.66 <= stats["hit_rate"] <= 0.67


class TestLRUCacheTTL:
    """Tests for TTL functionality."""

    def test_set_with_ttl(self):
        """Should accept custom TTL."""
        cache = LRUCache()
        cache.set("key1", "value1", ttl_seconds=30.0)

        result = cache.get("key1")
        assert result == "value1"


class TestLRUCacheContains:
    """Tests for cache containment checks."""

    def test_contains_existing_key(self):
        """Should return True for existing keys."""
        cache = LRUCache()
        cache.set("key1", "value1")
        assert cache.contains("key1") is True

    def test_contains_missing_key(self):
        """Should return False for missing keys."""
        cache = LRUCache()
        assert cache.contains("nonexistent") is False


class TestLRUCacheSize:
    """Tests for cache size tracking."""

    def test_size_tracking(self):
        """Should track cache size."""
        cache = LRUCache()
        cache.set("key1", "value1", size_bytes=100)
        cache.set("key2", "value2", size_bytes=200)

        stats = cache.stats()
        assert stats["size_bytes"] == 300

    def test_entry_count(self):
        """Should track entry count."""
        cache = LRUCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        stats = cache.stats()
        assert stats["entries"] == 3


class TestLRUCacheExpiration:
    """Tests for TTL expiration behavior."""

    def test_expired_entry_returns_none(self):
        """Expired entry should return None on get."""
        cache = LRUCache()
        # Create entry with very short TTL and manually backdate it
        cache.set("key1", "value1", ttl_seconds=0.01)
        time.sleep(0.02)  # Wait for expiration
        result = cache.get("key1")
        assert result is None

    def test_expired_entry_increments_miss(self):
        """Getting expired entry should count as miss."""
        cache = LRUCache()
        cache.set("key1", "value1", ttl_seconds=0.01)
        time.sleep(0.02)
        cache.get("key1")  # Should be a miss
        stats = cache.stats()
        assert stats["misses"] == 1

    def test_cleanup_expired_removes_old_entries(self):
        """cleanup_expired should remove expired entries."""
        cache = LRUCache()
        cache.set("key1", "value1", ttl_seconds=0.01)
        cache.set("key2", "value2", ttl_seconds=3600.0)  # Long TTL
        time.sleep(0.02)
        cache.cleanup_expired()
        assert cache.contains("key1") is False
        assert cache.contains("key2") is True

    def test_contains_removes_expired(self):
        """contains() should remove expired entries."""
        cache = LRUCache()
        cache.set("key1", "value1", ttl_seconds=0.01)
        time.sleep(0.02)
        assert cache.contains("key1") is False


class TestLRUCacheEviction:
    """Tests for eviction behavior."""

    def test_eviction_by_size(self):
        """Should evict when max size exceeded."""
        config = CacheConfig(max_size_bytes=200, max_entries=1000)
        cache = LRUCache(config=config)

        cache.set("key1", "value1", size_bytes=100)
        cache.set("key2", "value2", size_bytes=100)
        # Adding key3 should evict key1
        cache.set("key3", "value3", size_bytes=100)

        assert cache.get("key1") is None  # Evicted
        assert cache.get("key2") is not None or cache.get("key3") is not None

    def test_evict_expired_first(self):
        """Should evict expired entries before LRU."""
        config = CacheConfig(max_entries=2)
        cache = LRUCache(config=config)

        cache.set("key1", "value1", ttl_seconds=0.01)
        cache.set("key2", "value2", ttl_seconds=3600.0)
        time.sleep(0.02)

        # Adding key3 should evict expired key1, not key2
        cache.set("key3", "value3")

        assert cache.get("key1") is None  # Expired and evicted
        assert cache.get("key2") is not None
        assert cache.get("key3") is not None

    def test_update_existing_key(self):
        """Updating existing key should remove old entry first."""
        cache = LRUCache()
        cache.set("key1", "value1", size_bytes=100)
        cache.set("key1", "value2", size_bytes=50)  # Update

        assert cache.get("key1") == "value2"
        stats = cache.stats()
        assert stats["size_bytes"] == 50  # Not 150


class TestLRUCacheDeleteReturnValue:
    """Tests for delete return value."""

    def test_delete_returns_true_for_existing(self):
        """delete() should return True when key exists."""
        cache = LRUCache()
        cache.set("key1", "value1")
        result = cache.delete("key1")
        assert result is True

    def test_delete_returns_false_for_missing(self):
        """delete() should return False when key doesn't exist."""
        cache = LRUCache()
        result = cache.delete("nonexistent")
        assert result is False


class TestPageCache:
    """Tests for PageCache specialized cache."""

    def test_init(self):
        """PageCache should initialize correctly."""
        cache = PageCache()
        assert cache is not None

    def test_init_custom_max_pages(self):
        """PageCache should accept custom max pages."""
        cache = PageCache(max_pages=50)
        assert cache.config.max_entries == 50

    def test_cache_page_html(self):
        """Should cache page HTML."""
        cache = PageCache()
        cache.cache_page("https://example.com", "<html>Test</html>")
        html = cache.get_html("https://example.com")
        assert html == "<html>Test</html>"

    def test_cache_page_parsed(self):
        """Should cache parsed content."""
        cache = PageCache()
        parsed = {"title": "Test", "links": []}
        cache.cache_page("https://example.com", "<html>Test</html>", parsed=parsed)
        result = cache.get_parsed("https://example.com")
        assert result == parsed

    def test_get_html_missing(self):
        """Should return None for uncached URL."""
        cache = PageCache()
        result = cache.get_html("https://uncached.com")
        assert result is None

    def test_get_parsed_missing(self):
        """Should return None for uncached parsed."""
        cache = PageCache()
        result = cache.get_parsed("https://uncached.com")
        assert result is None

    def test_invalidate(self):
        """Should invalidate cached page."""
        cache = PageCache()
        parsed = {"title": "Test"}
        cache.cache_page("https://example.com", "<html>Test</html>", parsed=parsed)
        cache.invalidate("https://example.com")
        assert cache.get_html("https://example.com") is None
        assert cache.get_parsed("https://example.com") is None

    def test_get_stats(self):
        """Should return stats for both caches."""
        cache = PageCache()
        cache.cache_page("https://example.com", "<html>Test</html>")
        stats = cache.get_stats()
        assert "html_cache" in stats
        assert "parsed_cache" in stats


class TestResultCache:
    """Tests for ResultCache specialized cache."""

    def test_init(self):
        """ResultCache should initialize correctly."""
        cache = ResultCache()
        assert cache is not None

    def test_init_custom_max_queries(self):
        """ResultCache should accept custom max queries."""
        cache = ResultCache(max_queries=200)
        assert cache.config.max_entries == 200

    def test_cache_results(self):
        """Should cache search results."""
        cache = ResultCache()
        results = {"items": [1, 2, 3], "total": 3}
        cache.cache_results("test query", results)
        cached = cache.get_results("test query")
        assert cached == results

    def test_cache_results_with_source(self):
        """Should cache results with source."""
        cache = ResultCache()
        results = {"items": [1, 2, 3]}
        cache.cache_results("test query", results, source="google")
        cached = cache.get_results("test query", source="google")
        assert cached == results

    def test_different_sources_different_keys(self):
        """Same query with different sources should be cached separately."""
        cache = ResultCache()
        google_results = {"source": "google"}
        bing_results = {"source": "bing"}
        cache.cache_results("test query", google_results, source="google")
        cache.cache_results("test query", bing_results, source="bing")

        assert cache.get_results("test query", source="google") == google_results
        assert cache.get_results("test query", source="bing") == bing_results

    def test_query_normalization(self):
        """Query should be normalized (lowercase, stripped)."""
        cache = ResultCache()
        results = {"items": []}
        cache.cache_results("Test Query  ", results)
        # Should match with different casing/whitespace
        cached = cache.get_results("test query")
        assert cached == results

    def test_get_stats(self):
        """Should return cache stats."""
        cache = ResultCache()
        cache.cache_results("test", {"items": []})
        stats = cache.get_stats()
        assert "entries" in stats
        assert stats["entries"] == 1


class TestGlobalCacheInstances:
    """Tests for global cache instance functions."""

    def test_get_page_cache_returns_instance(self):
        """get_page_cache should return a PageCache instance."""
        cache = get_page_cache()
        assert isinstance(cache, PageCache)

    def test_get_page_cache_returns_same_instance(self):
        """get_page_cache should return singleton."""
        cache1 = get_page_cache()
        cache2 = get_page_cache()
        assert cache1 is cache2

    def test_get_result_cache_returns_instance(self):
        """get_result_cache should return a ResultCache instance."""
        cache = get_result_cache()
        assert isinstance(cache, ResultCache)

    def test_get_result_cache_returns_same_instance(self):
        """get_result_cache should return singleton."""
        cache1 = get_result_cache()
        cache2 = get_result_cache()
        assert cache1 is cache2


class TestLRUCachePersistence:
    """Tests for cache persistence functionality."""

    def test_persist_and_load(self):
        """Should persist and load cache to/from disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            persist_path = Path(tmpdir) / "cache.json"
            config = CacheConfig(persist=True, persist_path=persist_path)

            # Create cache and add data
            cache1 = LRUCache(config=config)
            cache1.set("key1", "value1", ttl_seconds=3600.0)
            cache1.set("key2", {"nested": "value"}, ttl_seconds=3600.0)
            cache1._save_to_disk()

            # Create new cache that loads from disk
            cache2 = LRUCache(config=config)

            assert cache2.get("key1") == "value1"
            assert cache2.get("key2") == {"nested": "value"}

    def test_load_handles_missing_file(self):
        """Should handle missing persist file gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            persist_path = Path(tmpdir) / "nonexistent.json"
            config = CacheConfig(persist=True, persist_path=persist_path)
            cache = LRUCache(config=config)
            # Should not raise, just have empty cache
            assert cache.stats()["entries"] == 0

    def test_load_handles_corrupt_file(self):
        """Should handle corrupt persist file gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            persist_path = Path(tmpdir) / "cache.json"
            persist_path.write_text("not valid json {{{")
            config = CacheConfig(persist=True, persist_path=persist_path)
            cache = LRUCache(config=config)
            # Should not raise, just have empty cache
            assert cache.stats()["entries"] == 0


class TestLRUCacheAPICompatibility:
    """Tests for API compatibility methods added for simpler test interface."""

    def test_stats_is_alias_for_get_stats(self):
        """stats() should be an alias for get_stats()."""
        cache = LRUCache()
        cache.set("key1", "value1")
        cache.get("key1")  # Hit
        cache.get("nonexistent")  # Miss

        stats1 = cache.stats()
        stats2 = cache.get_stats()

        assert stats1 == stats2
        assert stats1["hits"] == 1
        assert stats1["misses"] == 1

    def test_contains_existing_key(self):
        """contains() should return True for existing keys."""
        cache = LRUCache()
        cache.set("key1", "value1")
        assert cache.contains("key1") is True

    def test_contains_missing_key(self):
        """contains() should return False for missing keys."""
        cache = LRUCache()
        assert cache.contains("nonexistent") is False

    def test_contains_expired_key(self):
        """contains() should return False for expired keys."""
        cache = LRUCache()
        cache.set("key1", "value1", ttl_seconds=0.01)
        time.sleep(0.02)
        assert cache.contains("key1") is False

    def test_contains_does_not_increment_stats(self):
        """contains() should not affect hit/miss statistics."""
        cache = LRUCache()
        cache.set("key1", "value1")

        # Check stats before contains
        stats_before = cache.stats()

        # Call contains multiple times
        cache.contains("key1")
        cache.contains("key1")
        cache.contains("nonexistent")

        # Stats should not have changed
        stats_after = cache.stats()
        assert stats_before["hits"] == stats_after["hits"]
        assert stats_before["misses"] == stats_after["misses"]

    def test_stats_returns_all_fields(self):
        """stats() should return all expected fields."""
        cache = LRUCache()
        cache.set("key1", "value1", size_bytes=100)
        cache.get("key1")

        stats = cache.stats()

        assert "entries" in stats
        assert "size_bytes" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats
