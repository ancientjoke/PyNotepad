from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Callable, Any
from functools import lru_cache
import threading
import logging
import time
from collections import OrderedDict

from PyQt6.QtCore import QSize, QRectF, QPointF, Qt, QByteArray, QBuffer
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor, QTransform
from PyQt6.QtWidgets import QApplication

import fitz

from core.error_types import (
    Result,
    Success,
    Failure,
    RenderError,
    CacheError,
)
from core.pdf_engine import PDFDocument, PDFEngine, PageInfo

logger = logging.getLogger(__name__)


class ViewMode(Enum):
    """PDF viewing modes."""
    SINGLE_PAGE = auto()
    CONTINUOUS_SCROLL = auto()
    FACING_PAGES = auto()
    BOOK_VIEW = auto()


class ZoomMode(Enum):
    """Zoom fitting modes."""
    FIT_WIDTH = auto()
    FIT_PAGE = auto()
    ACTUAL_SIZE = auto()
    CUSTOM = auto()


@dataclass(frozen=True)
class RenderRequest:
    """Immutable render request specification."""
    
    document_hash: str
    page_number: int
    scale: float
    rotation: int = 0
    clip_rect: Optional[Tuple[float, float, float, float]] = None
    
    @property
    def cache_key(self) -> str:
        """Generate unique cache key for this render request."""
        clip_str = f"{self.clip_rect}" if self.clip_rect else "full"
        return f"{self.document_hash}:{self.page_number}:{self.scale:.3f}:{self.rotation}:{clip_str}"


@dataclass
class RenderResult:
    """Container for rendered page data."""
    
    request: RenderRequest
    image: QImage
    render_time_ms: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def memory_size_bytes(self) -> int:
        """Estimate memory usage of this render result."""
        return self.image.sizeInBytes()


@dataclass(frozen=True)
class TileSpec:
    """Specification for a render tile."""
    
    page_number: int
    tile_x: int
    tile_y: int
    tile_rect: Tuple[float, float, float, float]
    scale: float


class RenderCache:
    """
    LRU cache for rendered page images with configurable memory limit.
    Thread-safe implementation.
    """
    
    def __init__(self, max_memory_bytes: int = 200 * 1024 * 1024):
        self._max_memory_bytes = max_memory_bytes
        self._current_memory_bytes = 0
        self._cache: OrderedDict[str, RenderResult] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
        }
    
    def get(self, cache_key: str) -> Optional[RenderResult]:
        """
        Get a cached render result.
        
        Args:
            cache_key: The cache key to look up.
        
        Returns:
            The cached RenderResult or None if not found.
        """
        with self._lock:
            result = self._cache.get(cache_key)
            if result is not None:
                self._cache.move_to_end(cache_key)
                self._stats["hits"] += 1
                return result
            self._stats["misses"] += 1
            return None
    
    def put(self, cache_key: str, result: RenderResult) -> None:
        """
        Store a render result in the cache.
        
        Args:
            cache_key: The cache key.
            result: The render result to cache.
        """
        with self._lock:
            if cache_key in self._cache:
                old_result = self._cache[cache_key]
                self._current_memory_bytes -= old_result.memory_size_bytes
                del self._cache[cache_key]
            
            result_size = result.memory_size_bytes
            
            while (
                self._cache
                and self._current_memory_bytes + result_size > self._max_memory_bytes
            ):
                self._evict_oldest()
            
            if result_size <= self._max_memory_bytes:
                self._cache[cache_key] = result
                self._current_memory_bytes += result_size
    
    def _evict_oldest(self) -> None:
        """Evict the oldest (least recently used) entry."""
        if self._cache:
            oldest_key, oldest_result = self._cache.popitem(last=False)
            self._current_memory_bytes -= oldest_result.memory_size_bytes
            self._stats["evictions"] += 1
    
    def invalidate(self, document_hash: str) -> int:
        """
        Invalidate all cache entries for a document.
        
        Args:
            document_hash: The document hash to invalidate.
        
        Returns:
            Number of entries invalidated.
        """
        with self._lock:
            keys_to_remove = [
                key for key in self._cache.keys()
                if key.startswith(f"{document_hash}:")
            ]
            for key in keys_to_remove:
                result = self._cache.pop(key)
                self._current_memory_bytes -= result.memory_size_bytes
            return len(keys_to_remove)
    
    def invalidate_page(self, document_hash: str, page_number: int) -> int:
        """
        Invalidate all cache entries for a specific page.
        
        Args:
            document_hash: The document hash.
            page_number: The page number to invalidate.
        
        Returns:
            Number of entries invalidated.
        """
        with self._lock:
            prefix = f"{document_hash}:{page_number}:"
            keys_to_remove = [
                key for key in self._cache.keys()
                if key.startswith(prefix)
            ]
            for key in keys_to_remove:
                result = self._cache.pop(key)
                self._current_memory_bytes -= result.memory_size_bytes
            return len(keys_to_remove)
    
    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self._current_memory_bytes = 0
    
    @property
    def memory_usage_bytes(self) -> int:
        """Get current memory usage in bytes."""
        return self._current_memory_bytes
    
    @property
    def memory_usage_mb(self) -> float:
        """Get current memory usage in megabytes."""
        return self._current_memory_bytes / (1024 * 1024)
    
    @property
    def entry_count(self) -> int:
        """Get number of cached entries."""
        return len(self._cache)
    
    @property
    def statistics(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0.0
            return {
                **self._stats,
                "hit_rate": hit_rate,
                "entry_count": len(self._cache),
                "memory_usage_mb": self.memory_usage_mb,
                "max_memory_mb": self._max_memory_bytes / (1024 * 1024),
            }


class RenderEngine:
    """
    High-performance PDF rendering engine with caching and viewport optimization.
    """
    
    _instance: Optional[RenderEngine] = None
    _lock: threading.Lock = threading.Lock()
    
    TILE_SIZE = 512
    MIN_SCALE = 0.1
    MAX_SCALE = 5.0
    PRELOAD_PAGES = 2
    
    def __new__(cls, *args, **kwargs) -> RenderEngine:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        pdf_engine: Optional[PDFEngine] = None,
        cache_size_mb: int = 200,
    ):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._pdf_engine = pdf_engine or PDFEngine()
        self._cache = RenderCache(max_memory_bytes=cache_size_mb * 1024 * 1024)
        self._render_lock = threading.RLock()
        self._initialized = True
        
        logger.info(f"RenderEngine initialized with cache_size_mb={cache_size_mb}")
    
    def _fitz_pixmap_to_qimage(self, pixmap: fitz.Pixmap) -> QImage:
        """Convert PyMuPDF Pixmap to Qt QImage."""
        if pixmap.alpha:
            image_format = QImage.Format.Format_RGBA8888
        else:
            image_format = QImage.Format.Format_RGB888
        
        samples = pixmap.samples
        
        image = QImage(
            samples,
            pixmap.width,
            pixmap.height,
            pixmap.stride,
            image_format,
        )
        
        return image.copy()
    
    def render_page(
        self,
        document: PDFDocument,
        page_number: int,
        scale: float = 1.0,
        rotation: int = 0,
        use_cache: bool = True,
    ) -> Result[RenderResult]:
        """
        Render a full page at the specified scale.
        
        Args:
            document: The PDF document to render from.
            page_number: Zero-based page index.
            scale: Zoom scale factor (0.1 to 5.0).
            rotation: Rotation in degrees (0, 90, 180, 270).
            use_cache: Whether to use the render cache.
        
        Returns:
            Result containing RenderResult or error.
        """
        scale = max(self.MIN_SCALE, min(self.MAX_SCALE, scale))
        rotation = rotation % 360
        if rotation not in (0, 90, 180, 270):
            rotation = 0
        
        request = RenderRequest(
            document_hash=document.file_hash,
            page_number=page_number,
            scale=scale,
            rotation=rotation,
        )
        
        if use_cache:
            cached_result = self._cache.get(request.cache_key)
            if cached_result is not None:
                return Success(cached_result)
        
        start_time = time.perf_counter()
        
        pixmap_result = self._pdf_engine.render_page_to_pixmap(
            document,
            page_number,
            scale=scale,
            rotation=rotation,
        )
        
        if pixmap_result.is_failure():
            return Failure(RenderError(
                message=f"Failed to render page {page_number}",
                render_target=f"{document.file_path}:{page_number}",
            ))
        
        pixmap = pixmap_result.unwrap()
        image = self._fitz_pixmap_to_qimage(pixmap)
        
        render_time_ms = (time.perf_counter() - start_time) * 1000
        
        result = RenderResult(
            request=request,
            image=image,
            render_time_ms=render_time_ms,
        )
        
        if use_cache:
            self._cache.put(request.cache_key, result)
        
        logger.debug(
            f"Rendered page {page_number} at scale {scale:.2f} in {render_time_ms:.1f}ms"
        )
        
        return Success(result)
    
    def render_page_region(
        self,
        document: PDFDocument,
        page_number: int,
        region: Tuple[float, float, float, float],
        scale: float = 1.0,
        rotation: int = 0,
    ) -> Result[RenderResult]:
        """
        Render a specific region of a page (for viewport optimization).
        
        Args:
            document: The PDF document.
            page_number: Zero-based page index.
            region: Region to render (x0, y0, x1, y1) in page coordinates.
            scale: Zoom scale factor.
            rotation: Rotation in degrees.
        
        Returns:
            Result containing RenderResult or error.
        """
        scale = max(self.MIN_SCALE, min(self.MAX_SCALE, scale))
        
        request = RenderRequest(
            document_hash=document.file_hash,
            page_number=page_number,
            scale=scale,
            rotation=rotation,
            clip_rect=region,
        )
        
        cached_result = self._cache.get(request.cache_key)
        if cached_result is not None:
            return Success(cached_result)
        
        start_time = time.perf_counter()
        
        pixmap_result = self._pdf_engine.render_page_to_pixmap(
            document,
            page_number,
            scale=scale,
            rotation=rotation,
            clip_rect=region,
        )
        
        if pixmap_result.is_failure():
            return pixmap_result
        
        pixmap = pixmap_result.unwrap()
        image = self._fitz_pixmap_to_qimage(pixmap)
        
        render_time_ms = (time.perf_counter() - start_time) * 1000
        
        result = RenderResult(
            request=request,
            image=image,
            render_time_ms=render_time_ms,
        )
        
        self._cache.put(request.cache_key, result)
        
        return Success(result)
    
    def calculate_tiles_for_viewport(
        self,
        page_info: PageInfo,
        viewport_rect: QRectF,
        scale: float,
    ) -> List[TileSpec]:
        """
        Calculate which tiles are needed to cover the visible viewport.
        
        Args:
            page_info: Information about the page.
            viewport_rect: The visible viewport rectangle.
            scale: Current zoom scale.
        
        Returns:
            List of TileSpec objects for tiles that intersect the viewport.
        """
        page_width = page_info.width * scale
        page_height = page_info.height * scale
        
        tiles_x = int((page_width + self.TILE_SIZE - 1) // self.TILE_SIZE)
        tiles_y = int((page_height + self.TILE_SIZE - 1) // self.TILE_SIZE)
        
        needed_tiles: List[TileSpec] = []
        
        for tile_y in range(tiles_y):
            for tile_x in range(tiles_x):
                tile_rect_screen = QRectF(
                    tile_x * self.TILE_SIZE,
                    tile_y * self.TILE_SIZE,
                    self.TILE_SIZE,
                    self.TILE_SIZE,
                )
                
                if tile_rect_screen.intersects(viewport_rect):
                    tile_rect_page = (
                        tile_x * self.TILE_SIZE / scale,
                        tile_y * self.TILE_SIZE / scale,
                        (tile_x + 1) * self.TILE_SIZE / scale,
                        (tile_y + 1) * self.TILE_SIZE / scale,
                    )
                    
                    needed_tiles.append(TileSpec(
                        page_number=page_info.page_number,
                        tile_x=tile_x,
                        tile_y=tile_y,
                        tile_rect=tile_rect_page,
                        scale=scale,
                    ))
        
        return needed_tiles
    
    def calculate_fit_scale(
        self,
        page_info: PageInfo,
        viewport_size: QSize,
        zoom_mode: ZoomMode,
        margin: int = 10,
    ) -> float:
        """
        Calculate the scale factor for a zoom mode.
        
        Args:
            page_info: Information about the page.
            viewport_size: Size of the viewport.
            zoom_mode: The zoom fitting mode.
            margin: Margin around the page in pixels.
        
        Returns:
            The calculated scale factor.
        """
        available_width = viewport_size.width() - 2 * margin
        available_height = viewport_size.height() - 2 * margin
        
        if available_width <= 0 or available_height <= 0:
            return 1.0
        
        page_width = page_info.width
        page_height = page_info.height
        
        if page_info.rotation in (90, 270):
            page_width, page_height = page_height, page_width
        
        if zoom_mode == ZoomMode.FIT_WIDTH:
            scale = available_width / page_width
        elif zoom_mode == ZoomMode.FIT_PAGE:
            scale_width = available_width / page_width
            scale_height = available_height / page_height
            scale = min(scale_width, scale_height)
        elif zoom_mode == ZoomMode.ACTUAL_SIZE:
            scale = 1.0
        else:
            scale = 1.0
        
        return max(self.MIN_SCALE, min(self.MAX_SCALE, scale))
    
    def generate_thumbnail_qpixmap(
        self,
        document: PDFDocument,
        page_number: int = 0,
        max_dimension: int = 200,
    ) -> Result[QPixmap]:
        """
        Generate a thumbnail as a QPixmap.
        
        Args:
            document: The PDF document.
            page_number: Page to thumbnail.
            max_dimension: Maximum width or height.
        
        Returns:
            Result containing QPixmap thumbnail.
        """
        page_info_result = document.get_page_info(page_number)
        if page_info_result.is_failure():
            return page_info_result
        
        page_info = page_info_result.unwrap()
        
        scale = min(
            max_dimension / page_info.width,
            max_dimension / page_info.height,
        )
        
        render_result = self.render_page(
            document,
            page_number,
            scale=scale,
            use_cache=False,
        )
        
        if render_result.is_failure():
            return render_result
        
        result = render_result.unwrap()
        return Success(QPixmap.fromImage(result.image))
    
    def preload_pages(
        self,
        document: PDFDocument,
        current_page: int,
        scale: float,
        rotation: int = 0,
    ) -> None:
        """
        Preload pages around the current page for smoother scrolling.
        
        Args:
            document: The PDF document.
            current_page: Current page being viewed.
            scale: Current zoom scale.
            rotation: Current rotation.
        """
        pages_to_preload = []
        
        for offset in range(-self.PRELOAD_PAGES, self.PRELOAD_PAGES + 1):
            if offset == 0:
                continue
            page_num = current_page + offset
            if 0 <= page_num < document.page_count:
                pages_to_preload.append(page_num)
        
        for page_num in pages_to_preload:
            request = RenderRequest(
                document_hash=document.file_hash,
                page_number=page_num,
                scale=scale,
                rotation=rotation,
            )
            
            if self._cache.get(request.cache_key) is None:
                self.render_page(
                    document,
                    page_num,
                    scale=scale,
                    rotation=rotation,
                    use_cache=True,
                )
    
    def invalidate_document_cache(self, document_hash: str) -> int:
        """
        Invalidate all cached renders for a document.
        
        Args:
            document_hash: Hash of the document to invalidate.
        
        Returns:
            Number of entries invalidated.
        """
        return self._cache.invalidate(document_hash)
    
    def clear_cache(self) -> None:
        """Clear the entire render cache."""
        self._cache.clear()
    
    @property
    def cache_statistics(self) -> Dict[str, Any]:
        """Get render cache statistics."""
        return self._cache.statistics
