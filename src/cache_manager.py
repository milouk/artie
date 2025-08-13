"""Caching system for Artie Scraper to improve performance."""

# hashlib import removed - using simpler cache key generation
import json
import pickle
import time
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from logger import LoggerSingleton as logger


@dataclass
class CacheEntry:
    """Represents a cache entry with metadata."""

    data: Any
    timestamp: float
    ttl: float  # Time to live in seconds
    key: str

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return time.time() > (self.timestamp + self.ttl)

    def age_seconds(self) -> float:
        """Get age of cache entry in seconds."""
        return time.time() - self.timestamp


# HashCacheEntry class removed - no longer using hash caching


class CacheManager:
    """Manages caching for API responses, file operations, and computed data."""

    # Default TTL values in seconds
    DEFAULT_API_TTL = 3600  # 1 hour for API responses
    DEFAULT_FILE_TTL = 300  # 5 minutes for file operations
    DEFAULT_GAME_DATA_TTL = 86400  # 24 hours for game data
    # Hash TTL removed - no longer using hash caching

    def __init__(self, cache_dir: str = ".cache"):
        """
        Initialize cache manager.

        Args:
            cache_dir: Directory to store persistent cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        # In-memory caches
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._api_cache: Dict[str, CacheEntry] = {}
        self._file_cache: Dict[str, CacheEntry] = {}

        # Hash cache removed - no longer using hash functionality

        # Cache statistics
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "errors": 0,
            # Hash statistics removed
        }

        # Maximum cache sizes
        self.max_memory_entries = 1000
        self.max_api_entries = 500
        self.max_file_entries = 200
        # Hash cache size limit removed

        logger.log_info(
            f"Cache manager initialized with cache directory: {self.cache_dir}"
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = (
            (self._stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        )

        return {
            **self._stats,
            "hit_rate_percent": round(hit_rate, 2),
            "total_requests": total_requests,
            "memory_cache_size": len(self._memory_cache),
            "api_cache_size": len(self._api_cache),
            "file_cache_size": len(self._file_cache),
        }

    def _generate_cache_key(self, *args, **kwargs) -> str:
        """Generate a cache key from arguments."""
        key_data = {"args": args, "kwargs": sorted(kwargs.items()) if kwargs else {}}
        key_string = json.dumps(key_data, sort_keys=True, default=str)
        # Use simple hash() function instead of MD5 for cache keys
        return str(abs(hash(key_string)))

    def _cleanup_expired_entries(self, cache_dict: Dict[str, CacheEntry]) -> None:
        """Remove expired entries from a cache dictionary."""
        expired_keys = [key for key, entry in cache_dict.items() if entry.is_expired()]

        for key in expired_keys:
            del cache_dict[key]
            self._stats["evictions"] += 1

        if expired_keys:
            logger.log_info(f"Cleaned up {len(expired_keys)} expired cache entries")

    def _enforce_cache_size_limit(
        self, cache_dict: Dict[str, CacheEntry], max_size: int
    ) -> None:
        """Enforce cache size limits by removing oldest entries."""
        if len(cache_dict) <= max_size:
            return

        # Sort by timestamp (oldest first)
        sorted_entries = sorted(cache_dict.items(), key=lambda x: x[1].timestamp)
        entries_to_remove = len(cache_dict) - max_size

        for key, _ in sorted_entries[:entries_to_remove]:
            del cache_dict[key]
            self._stats["evictions"] += 1

        if entries_to_remove > 0:
            logger.log_info(
                f"Evicted {entries_to_remove} entries to enforce cache size limit"
            )

    def get(self, key: str, cache_type: str = "memory") -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key
            cache_type: Type of cache ("memory", "api", "file")

        Returns:
            Cached value or None if not found/expired
        """
        try:
            cache_dict = self._get_cache_dict(cache_type)

            if key not in cache_dict:
                self._stats["misses"] += 1
                return None

            entry = cache_dict[key]

            if entry.is_expired():
                del cache_dict[key]
                self._stats["misses"] += 1
                self._stats["evictions"] += 1
                return None

            self._stats["hits"] += 1
            return entry.data

        except Exception as e:
            logger.log_error(f"Error getting cache entry {key}: {e}")
            self._stats["errors"] += 1
            return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        cache_type: str = "memory",
    ) -> None:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default if None)
            cache_type: Type of cache ("memory", "api", "file")
        """
        try:
            cache_dict = self._get_cache_dict(cache_type)
            max_size = self._get_max_size(cache_type)
            default_ttl = self._get_default_ttl(cache_type)

            entry = CacheEntry(
                data=value, timestamp=time.time(), ttl=ttl or default_ttl, key=key
            )

            cache_dict[key] = entry

            # Cleanup and enforce limits
            self._cleanup_expired_entries(cache_dict)
            self._enforce_cache_size_limit(cache_dict, max_size)

        except Exception as e:
            logger.log_error(f"Error setting cache entry {key}: {e}")
            self._stats["errors"] += 1

    def _get_cache_dict(self, cache_type: str) -> Dict[str, CacheEntry]:
        """Get the appropriate cache dictionary."""
        if cache_type == "api":
            return self._api_cache
        elif cache_type == "file":
            return self._file_cache
        else:
            return self._memory_cache

    def _get_max_size(self, cache_type: str) -> int:
        """Get maximum size for cache type."""
        if cache_type == "api":
            return self.max_api_entries
        elif cache_type == "file":
            return self.max_file_entries
        else:
            return self.max_memory_entries

    def _get_default_ttl(self, cache_type: str) -> float:
        """Get default TTL for cache type."""
        if cache_type == "api":
            return self.DEFAULT_API_TTL
        elif cache_type == "file":
            return self.DEFAULT_FILE_TTL
        else:
            return self.DEFAULT_GAME_DATA_TTL

    def invalidate(self, key: str, cache_type: str = "memory") -> bool:
        """
        Invalidate a specific cache entry.

        Args:
            key: Cache key to invalidate
            cache_type: Type of cache

        Returns:
            True if entry was found and removed, False otherwise
        """
        try:
            cache_dict = self._get_cache_dict(cache_type)

            if key in cache_dict:
                del cache_dict[key]
                return True

            return False

        except Exception as e:
            logger.log_error(f"Error invalidating cache entry {key}: {e}")
            self._stats["errors"] += 1
            return False

    def clear(self, cache_type: Optional[str] = None) -> None:
        """
        Clear cache entries.

        Args:
            cache_type: Type of cache to clear (None for all)
        """
        try:
            if cache_type is None:
                # Clear all caches
                self._memory_cache.clear()
                self._api_cache.clear()
                self._file_cache.clear()
                logger.log_info("Cleared all caches")
            else:
                cache_dict = self._get_cache_dict(cache_type)
                cache_dict.clear()
                logger.log_info(f"Cleared {cache_type} cache")

        except Exception as e:
            logger.log_error(f"Error clearing cache: {e}")
            self._stats["errors"] += 1

    def save_to_disk(self, cache_type: str = "api") -> None:
        """
        Save cache to disk for persistence.

        Args:
            cache_type: Type of cache to save
        """
        try:
            cache_dict = self._get_cache_dict(cache_type)
            cache_file = self.cache_dir / f"{cache_type}_cache.pkl"

            # Filter out expired entries before saving
            valid_entries = {
                key: entry
                for key, entry in cache_dict.items()
                if not entry.is_expired()
            }

            with open(cache_file, "wb") as f:
                pickle.dump(valid_entries, f)

            logger.log_info(
                f"Saved {len(valid_entries)} {cache_type} cache entries to disk"
            )

        except Exception as e:
            logger.log_error(f"Error saving {cache_type} cache to disk: {e}")
            self._stats["errors"] += 1

    def load_from_disk(self, cache_type: str = "api") -> None:
        """
        Load cache from disk.

        Args:
            cache_type: Type of cache to load
        """
        try:
            cache_file = self.cache_dir / f"{cache_type}_cache.pkl"

            if not cache_file.exists():
                return

            with open(cache_file, "rb") as f:
                loaded_entries = pickle.load(f)

            # Filter out expired entries
            cache_dict = self._get_cache_dict(cache_type)
            valid_count = 0

            for key, entry in loaded_entries.items():
                if not entry.is_expired():
                    cache_dict[key] = entry
                    valid_count += 1

            logger.log_info(
                f"Loaded {valid_count} valid {cache_type} cache entries from disk"
            )

        except Exception as e:
            logger.log_error(f"Error loading {cache_type} cache from disk: {e}")
            self._stats["errors"] += 1

    # Hash cache methods removed - no longer using hash functionality

    def save_all_caches(self) -> None:
        """Save all persistent caches to disk."""
        self.save_to_disk("api")
        logger.log_info("All caches saved to disk")


def cached(
    ttl: Optional[float] = None,
    cache_type: str = "memory",
    key_func: Optional[Callable] = None,
):
    """
    Decorator for caching function results.

    Args:
        ttl: Time to live in seconds
        cache_type: Type of cache to use
        key_func: Custom function to generate cache key
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get cache manager from global scope or create one
            cache_manager = getattr(wrapper, "_cache_manager", None)
            if cache_manager is None:
                cache_manager = get_cache_manager()
                wrapper._cache_manager = cache_manager

            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = cache_manager._generate_cache_key(
                    func.__name__, *args, **kwargs
                )

            # Try to get from cache
            cached_result = cache_manager.get(cache_key, cache_type)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            try:
                result = func(*args, **kwargs)
                cache_manager.set(cache_key, result, ttl, cache_type)
                return result
            except Exception as e:
                logger.log_error(f"Error in cached function {func.__name__}: {e}")
                raise

        return wrapper

    return decorator


# Convenience decorators for common use cases
def api_cached(ttl: Optional[float] = None):
    """Decorator for caching API responses."""
    return cached(ttl=ttl or CacheManager.DEFAULT_API_TTL, cache_type="api")


def file_cached(ttl: Optional[float] = None):
    """Decorator for caching file operations."""
    return cached(ttl=ttl or CacheManager.DEFAULT_FILE_TTL, cache_type="file")


# Global cache manager instance
_global_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get global cache manager instance."""
    global _global_cache_manager
    if _global_cache_manager is None:
        _global_cache_manager = CacheManager()
    return _global_cache_manager
