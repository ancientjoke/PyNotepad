"""
Cache Service

Manages caching for rendered pages, thumbnails, and other resources.
Provides unified cache management with memory and disk tiers.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any, Callable, TypeVar
from collections import OrderedDict
import threading
import time
import hashlib
import pickle
import shutil

from core.error_types import (
    Result,
    Success,
    Failure,
    CacheError,
)

T = TypeVar('T')


@dataclass
class CacheEntry:
    """Represents a cached item with metadata."""
    
    key: str
    value: Any
    size_bytes: int
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    ttl_seconds: Optional[float] = None
    
    @property
    def is_expired(self) -> bool:
        """Check if the entry has expired."""
        if self.ttl_seconds is None:
            return False
        return time.time() - self.created_at > self.ttl_seconds
    
    def touch(self) -> None:
        """Update last accessed time and increment access count."""
        self.last_accessed = time.time()
        self.access_count += 1


@dataclass
class CacheStats:
    """Statistics for cache performance monitoring."""
    
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_size_bytes: int = 0
    entry_count: int = 0
    max_size_bytes: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    @property
    def usage_percent(self) -> float:
        """Calculate memory usage percentage."""
        return (self.total_size_bytes / self.max_size_bytes * 100 
                if self.max_size_bytes > 0 else 0.0)


class MemoryCache:
    """
    LRU memory cache with size-based eviction.
    
    Thread-safe implementation using OrderedDict for LRU ordering.
    """
    
    def __init__(
        self,
        max_size_bytes: int = 200 * 1024 * 1024,  # 200 MB default
        max_entries: int = 1000,
    ):
        self._max_size_bytes = max_size_bytes
        self._max_entries = max_entries
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._current_size_bytes = 0
        self._lock = threading.RLock()
        self._stats = CacheStats(max_size_bytes=max_size_bytes)
    
    def get(self, key: str) -> Result[Any]:
        """
        Get an item from the cache.
        
        Args:
            key: Cache key.
        
        Returns:
            Result containing the cached value or cache miss error.
        """
        with self._lock:
            if key not in self._cache:
                self._stats.misses += 1
                return Failure(CacheError(
                    message="Cache miss",
                    cache_key=key,
                ))
            
            entry = self._cache[key]
            
            if entry.is_expired:
                self._remove_entry(key)
                self._stats.misses += 1
                return Failure(CacheError(
                    message="Cache entry expired",
                    cache_key=key,
                ))
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.touch()
            self._stats.hits += 1
            
            return Success(entry.value)
    
    def put(
        self,
        key: str,
        value: Any,
        size_bytes: Optional[int] = None,
        ttl_seconds: Optional[float] = None,
    ) -> Result[None]:
        """
        Put an item into the cache.
        
        Args:
            key: Cache key.
            value: Value to cache.
            size_bytes: Size of the value in bytes (estimated if not provided).
            ttl_seconds: Time to live in seconds.
        
        Returns:
            Result indicating success or failure.
        """
        if size_bytes is None:
            size_bytes = self._estimate_size(value)
        
        if size_bytes > self._max_size_bytes:
            return Failure(CacheError(
                message="Value too large for cache",
                cache_key=key,
            ))
        
        with self._lock:
            # Remove existing entry if present
            if key in self._cache:
                self._remove_entry(key)
            
            # Evict entries if needed
            while (self._current_size_bytes + size_bytes > self._max_size_bytes 
                   or len(self._cache) >= self._max_entries):
                if not self._cache:
                    break
                self._evict_lru()
            
            # Add new entry
            entry = CacheEntry(
                key=key,
                value=value,
                size_bytes=size_bytes,
                ttl_seconds=ttl_seconds,
            )
            self._cache[key] = entry
            self._current_size_bytes += size_bytes
            self._stats.entry_count = len(self._cache)
            self._stats.total_size_bytes = self._current_size_bytes
            
            return Success(None)
    
    def remove(self, key: str) -> Result[None]:
        """Remove an item from the cache."""
        with self._lock:
            if key not in self._cache:
                return Failure(CacheError(
                    message="Key not found",
                    cache_key=key,
                ))
            
            self._remove_entry(key)
            return Success(None)
    
    def clear(self) -> None:
        """Clear all entries from the cache."""
        with self._lock:
            self._cache.clear()
            self._current_size_bytes = 0
            self._stats.entry_count = 0
            self._stats.total_size_bytes = 0
    
    def clear_expired(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""
        removed = 0
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired
            ]
            for key in expired_keys:
                self._remove_entry(key)
                removed += 1
        return removed
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        with self._lock:
            return CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                evictions=self._stats.evictions,
                total_size_bytes=self._current_size_bytes,
                entry_count=len(self._cache),
                max_size_bytes=self._max_size_bytes,
            )
    
    def contains(self, key: str) -> bool:
        """Check if a key exists in the cache."""
        with self._lock:
            if key not in self._cache:
                return False
            entry = self._cache[key]
            if entry.is_expired:
                self._remove_entry(key)
                return False
            return True
    
    def _remove_entry(self, key: str) -> None:
        """Remove an entry and update size tracking."""
        if key in self._cache:
            entry = self._cache.pop(key)
            self._current_size_bytes -= entry.size_bytes
    
    def _evict_lru(self) -> None:
        """Evict the least recently used entry."""
        if self._cache:
            # Get first item (least recently used)
            key = next(iter(self._cache))
            self._remove_entry(key)
            self._stats.evictions += 1
    
    def _estimate_size(self, value: Any) -> int:
        """Estimate the size of a value in bytes."""
        try:
            return len(pickle.dumps(value))
        except Exception:
            # Fallback to a reasonable default
            return 1024


class DiskCache:
    """
    Persistent disk cache for larger items.
    
    Uses a directory-based storage with hash-based filenames.
    """
    
    def __init__(
        self,
        cache_dir: Path,
        max_size_bytes: int = 1024 * 1024 * 1024,  # 1 GB default
        max_age_days: int = 30,
    ):
        self._cache_dir = cache_dir
        self._max_size_bytes = max_size_bytes
        self._max_age_seconds = max_age_days * 24 * 60 * 60
        self._lock = threading.RLock()
        self._metadata_file = cache_dir / ".cache_metadata"
        
        # Ensure cache directory exists
        self._cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get(self, key: str) -> Result[bytes]:
        """
        Get an item from the disk cache.
        
        Args:
            key: Cache key.
        
        Returns:
            Result containing the cached bytes or error.
        """
        file_path = self._key_to_path(key)
        
        with self._lock:
            if not file_path.exists():
                return Failure(CacheError(
                    message="Cache miss",
                    cache_key=key,
                ))
            
            # Check age
            age = time.time() - file_path.stat().st_mtime
            if age > self._max_age_seconds:
                file_path.unlink(missing_ok=True)
                return Failure(CacheError(
                    message="Cache entry expired",
                    cache_key=key,
                ))
            
            try:
                return Success(file_path.read_bytes())
            except Exception as e:
                return Failure(CacheError(
                    message=f"Failed to read cache: {e}",
                    cache_key=key,
                ))
    
    def put(self, key: str, data: bytes) -> Result[None]:
        """
        Put an item into the disk cache.
        
        Args:
            key: Cache key.
            data: Bytes to cache.
        
        Returns:
            Result indicating success or failure.
        """
        file_path = self._key_to_path(key)
        
        with self._lock:
            # Ensure space is available
            self._ensure_space(len(data))
            
            try:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_bytes(data)
                return Success(None)
            except Exception as e:
                return Failure(CacheError(
                    message=f"Failed to write cache: {e}",
                    cache_key=key,
                ))
    
    def remove(self, key: str) -> Result[None]:
        """Remove an item from the disk cache."""
        file_path = self._key_to_path(key)
        
        with self._lock:
            if not file_path.exists():
                return Failure(CacheError(
                    message="Key not found",
                    cache_key=key,
                ))
            
            try:
                file_path.unlink()
                return Success(None)
            except Exception as e:
                return Failure(CacheError(
                    message=f"Failed to delete cache: {e}",
                    cache_key=key,
                ))
    
    def clear(self) -> None:
        """Clear all cached files."""
        with self._lock:
            if self._cache_dir.exists():
                shutil.rmtree(self._cache_dir)
            self._cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get_size(self) -> int:
        """Get the total size of cached files in bytes."""
        total = 0
        with self._lock:
            for file in self._cache_dir.rglob("*"):
                if file.is_file() and file.name != ".cache_metadata":
                    total += file.stat().st_size
        return total
    
    def _key_to_path(self, key: str) -> Path:
        """Convert a cache key to a file path."""
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        # Use first 2 chars as subdirectory for better distribution
        return self._cache_dir / key_hash[:2] / key_hash
    
    def _ensure_space(self, required_bytes: int) -> None:
        """Ensure enough space is available, evicting old entries if needed."""
        current_size = self.get_size()
        
        if current_size + required_bytes <= self._max_size_bytes:
            return
        
        # Get all cache files sorted by modification time
        files = []
        for file in self._cache_dir.rglob("*"):
            if file.is_file() and file.name != ".cache_metadata":
                files.append((file, file.stat().st_mtime, file.stat().st_size))
        
        files.sort(key=lambda x: x[1])  # Sort by mtime (oldest first)
        
        # Remove oldest files until we have enough space
        for file, _, size in files:
            if current_size + required_bytes <= self._max_size_bytes:
                break
            try:
                file.unlink()
                current_size -= size
            except Exception:
                pass


class CacheService:
    """
    Unified cache service with memory and disk tiers.
    
    Provides a simple interface for caching with automatic tier management.
    """
    
    _instance: Optional[CacheService] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> CacheService:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        
        # Memory caches for different purposes
        self._page_cache = MemoryCache(
            max_size_bytes=200 * 1024 * 1024,  # 200 MB for rendered pages
            max_entries=500,
        )
        self._thumbnail_cache = MemoryCache(
            max_size_bytes=50 * 1024 * 1024,  # 50 MB for thumbnails
            max_entries=1000,
        )
        self._metadata_cache = MemoryCache(
            max_size_bytes=10 * 1024 * 1024,  # 10 MB for metadata
            max_entries=2000,
        )
        
        # Disk cache for persistent storage
        self._disk_cache: Optional[DiskCache] = None
    
    def initialize_disk_cache(self, cache_dir: Path) -> Result[None]:
        """Initialize the disk cache with the given directory."""
        try:
            self._disk_cache = DiskCache(cache_dir)
            return Success(None)
        except Exception as e:
            return Failure(CacheError(
                message=f"Failed to initialize disk cache: {e}",
            ))
    
    # Page cache operations
    def cache_page(
        self,
        document_id: str,
        page_number: int,
        zoom: float,
        image_data: Any,
        size_bytes: Optional[int] = None,
    ) -> Result[None]:
        """Cache a rendered page."""
        key = f"page:{document_id}:{page_number}:{zoom:.2f}"
        return self._page_cache.put(key, image_data, size_bytes)
    
    def get_cached_page(
        self,
        document_id: str,
        page_number: int,
        zoom: float,
    ) -> Result[Any]:
        """Get a cached rendered page."""
        key = f"page:{document_id}:{page_number}:{zoom:.2f}"
        return self._page_cache.get(key)
    
    def invalidate_document_pages(self, document_id: str) -> None:
        """Invalidate all cached pages for a document."""
        prefix = f"page:{document_id}:"
        keys_to_remove = [
            key for key in list(self._page_cache._cache.keys())
            if key.startswith(prefix)
        ]
        for key in keys_to_remove:
            self._page_cache.remove(key)
    
    # Thumbnail cache operations
    def cache_thumbnail(
        self,
        document_id: str,
        page_number: int,
        thumbnail_data: Any,
        size_bytes: Optional[int] = None,
    ) -> Result[None]:
        """Cache a page thumbnail."""
        key = f"thumb:{document_id}:{page_number}"
        return self._thumbnail_cache.put(key, thumbnail_data, size_bytes)
    
    def get_cached_thumbnail(
        self,
        document_id: str,
        page_number: int,
    ) -> Result[Any]:
        """Get a cached thumbnail."""
        key = f"thumb:{document_id}:{page_number}"
        return self._thumbnail_cache.get(key)
    
    # Metadata cache operations
    def cache_metadata(
        self,
        document_id: str,
        metadata: Any,
    ) -> Result[None]:
        """Cache document metadata."""
        key = f"meta:{document_id}"
        return self._metadata_cache.put(key, metadata)
    
    def get_cached_metadata(self, document_id: str) -> Result[Any]:
        """Get cached document metadata."""
        key = f"meta:{document_id}"
        return self._metadata_cache.get(key)
    
    # Disk cache operations
    def cache_to_disk(self, key: str, data: bytes) -> Result[None]:
        """Cache data to disk."""
        if self._disk_cache is None:
            return Failure(CacheError(message="Disk cache not initialized"))
        return self._disk_cache.put(key, data)
    
    def get_from_disk(self, key: str) -> Result[bytes]:
        """Get data from disk cache."""
        if self._disk_cache is None:
            return Failure(CacheError(message="Disk cache not initialized"))
        return self._disk_cache.get(key)
    
    # Cache management
    def clear_all(self) -> None:
        """Clear all caches."""
        self._page_cache.clear()
        self._thumbnail_cache.clear()
        self._metadata_cache.clear()
        if self._disk_cache:
            self._disk_cache.clear()
    
    def clear_memory(self) -> None:
        """Clear only memory caches."""
        self._page_cache.clear()
        self._thumbnail_cache.clear()
        self._metadata_cache.clear()
    
    def get_memory_usage(self) -> dict[str, CacheStats]:
        """Get memory usage statistics for all caches."""
        return {
            "pages": self._page_cache.get_stats(),
            "thumbnails": self._thumbnail_cache.get_stats(),
            "metadata": self._metadata_cache.get_stats(),
        }
    
    def get_disk_usage(self) -> int:
        """Get disk cache usage in bytes."""
        if self._disk_cache:
            return self._disk_cache.get_size()
        return 0
    
    def cleanup_expired(self) -> dict[str, int]:
        """Remove expired entries from all caches."""
        return {
            "pages": self._page_cache.clear_expired(),
            "thumbnails": self._thumbnail_cache.clear_expired(),
            "metadata": self._metadata_cache.clear_expired(),
        }
