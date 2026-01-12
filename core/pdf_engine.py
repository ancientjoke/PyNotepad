from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from functools import lru_cache
import hashlib
import logging
import threading

import fitz

from core.error_types import (
    Result,
    Success,
    Failure,
    PDFError,
    PDFLoadError,
    PDFRenderError,
    PDFCorruptError,
    PDFPasswordError,
    try_execute,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PDFMetadata:
    """Immutable container for PDF document metadata."""
    
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    keywords: Optional[str] = None
    creator: Optional[str] = None
    producer: Optional[str] = None
    creation_date: Optional[datetime] = None
    modification_date: Optional[datetime] = None
    page_count: int = 0
    file_size_bytes: int = 0
    is_encrypted: bool = False
    is_linearized: bool = False
    pdf_version: Optional[str] = None


@dataclass(frozen=True)
class PageInfo:
    """Immutable container for PDF page information."""
    
    page_number: int
    width: float
    height: float
    rotation: int = 0
    media_box: Tuple[float, float, float, float] = (0, 0, 0, 0)
    crop_box: Optional[Tuple[float, float, float, float]] = None
    has_text: bool = False
    has_images: bool = False
    has_annotations: bool = False


@dataclass
class PDFDocument:
    """Wrapper around PyMuPDF document with resource management."""
    
    file_path: Path
    file_hash: str
    document: fitz.Document
    metadata: PDFMetadata
    page_info_cache: Dict[int, PageInfo] = field(default_factory=dict)
    _lock: threading.RLock = field(default_factory=threading.RLock)
    
    def __del__(self):
        self.close()
    
    def close(self) -> None:
        """Close the underlying PDF document."""
        with self._lock:
            if hasattr(self, 'document') and self.document is not None:
                try:
                    self.document.close()
                except Exception:
                    pass
    
    def is_open(self) -> bool:
        """Check if the document is still open."""
        return self.document is not None and not self.document.is_closed
    
    @property
    def page_count(self) -> int:
        """Get the total number of pages."""
        return len(self.document) if self.is_open() else 0
    
    def get_page_info(self, page_number: int) -> Result[PageInfo]:
        """
        Get information about a specific page.
        
        Args:
            page_number: Zero-based page index.
        
        Returns:
            Result containing PageInfo or error.
        """
        if not self.is_open():
            return Failure(PDFError(message="Document is closed"))
        
        if page_number < 0 or page_number >= self.page_count:
            return Failure(PDFError(
                message=f"Page number {page_number} out of range (0-{self.page_count - 1})",
                page_number=page_number,
            ))
        
        with self._lock:
            if page_number in self.page_info_cache:
                return Success(self.page_info_cache[page_number])
            
            try:
                page = self.document[page_number]
                rect = page.rect
                media_box = page.mediabox
                crop_box = page.cropbox if page.cropbox != media_box else None
                
                text_blocks = page.get_text("blocks")
                images = page.get_images()
                annots = list(page.annots()) if page.annots() else []
                
                page_info = PageInfo(
                    page_number=page_number,
                    width=rect.width,
                    height=rect.height,
                    rotation=page.rotation,
                    media_box=(media_box.x0, media_box.y0, media_box.x1, media_box.y1),
                    crop_box=(crop_box.x0, crop_box.y0, crop_box.x1, crop_box.y1) if crop_box else None,
                    has_text=len(text_blocks) > 0,
                    has_images=len(images) > 0,
                    has_annotations=len(annots) > 0,
                )
                
                self.page_info_cache[page_number] = page_info
                return Success(page_info)
                
            except Exception as exception:
                return Failure(PDFError(
                    message=f"Failed to get page info: {str(exception)}",
                    file_path=self.file_path,
                    page_number=page_number,
                ))
    
    def get_page_text(self, page_number: int) -> Result[str]:
        """
        Extract text content from a page.
        
        Args:
            page_number: Zero-based page index.
        
        Returns:
            Result containing extracted text or error.
        """
        if not self.is_open():
            return Failure(PDFError(message="Document is closed"))
        
        if page_number < 0 or page_number >= self.page_count:
            return Failure(PDFError(
                message=f"Page number {page_number} out of range",
                page_number=page_number,
            ))
        
        with self._lock:
            try:
                page = self.document[page_number]
                text = page.get_text("text")
                return Success(text)
            except Exception as exception:
                return Failure(PDFError(
                    message=f"Failed to extract text: {str(exception)}",
                    file_path=self.file_path,
                    page_number=page_number,
                ))
    
    def search_text(
        self,
        search_term: str,
        page_number: Optional[int] = None,
    ) -> Result[List[Tuple[int, fitz.Rect]]]:
        """
        Search for text in the document.
        
        Args:
            search_term: Text to search for.
            page_number: Optional specific page to search. Searches all pages if None.
        
        Returns:
            Result containing list of (page_number, rectangle) tuples.
        """
        if not self.is_open():
            return Failure(PDFError(message="Document is closed"))
        
        results: List[Tuple[int, fitz.Rect]] = []
        
        with self._lock:
            try:
                pages_to_search = range(self.page_count)
                if page_number is not None:
                    if page_number < 0 or page_number >= self.page_count:
                        return Success([])
                    pages_to_search = [page_number]
                
                for page_num in pages_to_search:
                    page = self.document[page_num]
                    text_instances = page.search_for(search_term)
                    for rect in text_instances:
                        results.append((page_num, rect))
                
                return Success(results)
                
            except Exception as exception:
                return Failure(PDFError(
                    message=f"Search failed: {str(exception)}",
                    file_path=self.file_path,
                ))


class PDFEngine:
    """
    High-level PDF engine providing document loading, caching, and management.
    Thread-safe singleton with configurable cache size.
    """
    
    _instance: Optional[PDFEngine] = None
    _lock: threading.Lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs) -> PDFEngine:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, max_open_documents: int = 10):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._max_open_documents = max_open_documents
        self._open_documents: Dict[str, PDFDocument] = {}
        self._document_access_order: List[str] = []
        self._documents_lock = threading.RLock()
        self._initialized = True
        
        logger.info(f"PDFEngine initialized with max_open_documents={max_open_documents}")
    
    def _compute_file_hash(self, file_path: Path) -> Result[str]:
        """Compute SHA-256 hash of a file."""
        try:
            hasher = hashlib.sha256()
            with open(file_path, 'rb') as file:
                for chunk in iter(lambda: file.read(65536), b''):
                    hasher.update(chunk)
            return Success(hasher.hexdigest())
        except FileNotFoundError:
            return Failure(PDFLoadError(
                message=f"File not found: {file_path}",
                file_path=file_path,
            ))
        except PermissionError:
            return Failure(PDFLoadError(
                message=f"Permission denied: {file_path}",
                file_path=file_path,
            ))
        except Exception as exception:
            return Failure(PDFLoadError(
                message=f"Failed to compute file hash: {str(exception)}",
                file_path=file_path,
            ))
    
    def _parse_pdf_date(self, date_string: Optional[str]) -> Optional[datetime]:
        """Parse PDF date format to datetime."""
        if not date_string:
            return None
        
        try:
            date_string = date_string.strip()
            if date_string.startswith("D:"):
                date_string = date_string[2:]
            
            if len(date_string) >= 14:
                return datetime.strptime(date_string[:14], "%Y%m%d%H%M%S")
            elif len(date_string) >= 8:
                return datetime.strptime(date_string[:8], "%Y%m%d")
        except ValueError:
            pass
        
        return None
    
    def _extract_metadata(
        self,
        document: fitz.Document,
        file_path: Path,
        file_size: int,
    ) -> PDFMetadata:
        """Extract metadata from a PDF document."""
        metadata = document.metadata or {}
        
        return PDFMetadata(
            title=metadata.get("title") or None,
            author=metadata.get("author") or None,
            subject=metadata.get("subject") or None,
            keywords=metadata.get("keywords") or None,
            creator=metadata.get("creator") or None,
            producer=metadata.get("producer") or None,
            creation_date=self._parse_pdf_date(metadata.get("creationDate")),
            modification_date=self._parse_pdf_date(metadata.get("modDate")),
            page_count=len(document),
            file_size_bytes=file_size,
            is_encrypted=document.is_encrypted,
            is_linearized=document.is_fast_webaccess,
            pdf_version=f"{document.metadata.get('format', 'PDF')}",
        )
    
    def _evict_oldest_document(self) -> None:
        """Evict the least recently used document from cache."""
        with self._documents_lock:
            if not self._document_access_order:
                return
            
            oldest_hash = self._document_access_order.pop(0)
            if oldest_hash in self._open_documents:
                document = self._open_documents.pop(oldest_hash)
                document.close()
                logger.debug(f"Evicted document: {document.file_path}")
    
    def _update_access_order(self, file_hash: str) -> None:
        """Update the access order for LRU eviction."""
        with self._documents_lock:
            if file_hash in self._document_access_order:
                self._document_access_order.remove(file_hash)
            self._document_access_order.append(file_hash)
    
    def load_document(
        self,
        file_path: Path,
        password: Optional[str] = None,
    ) -> Result[PDFDocument]:
        """
        Load a PDF document with caching.
        
        Args:
            file_path: Path to the PDF file.
            password: Optional password for encrypted PDFs.
        
        Returns:
            Result containing PDFDocument or error.
        """
        file_path = Path(file_path).resolve()
        
        if not file_path.exists():
            return Failure(PDFLoadError(
                message=f"File not found: {file_path}",
                file_path=file_path,
            ))
        
        if not file_path.is_file():
            return Failure(PDFLoadError(
                message=f"Path is not a file: {file_path}",
                file_path=file_path,
            ))
        
        if file_path.suffix.lower() != '.pdf':
            return Failure(PDFLoadError(
                message=f"File is not a PDF: {file_path}",
                file_path=file_path,
            ))
        
        hash_result = self._compute_file_hash(file_path)
        if hash_result.is_failure():
            return hash_result
        
        file_hash = hash_result.unwrap()
        
        with self._documents_lock:
            if file_hash in self._open_documents:
                document = self._open_documents[file_hash]
                if document.is_open():
                    self._update_access_order(file_hash)
                    logger.debug(f"Returning cached document: {file_path}")
                    return Success(document)
                else:
                    del self._open_documents[file_hash]
                    if file_hash in self._document_access_order:
                        self._document_access_order.remove(file_hash)
        
        try:
            fitz_document = fitz.open(file_path)
            
            if fitz_document.is_encrypted:
                if password is None:
                    fitz_document.close()
                    return Failure(PDFPasswordError(
                        message="PDF is encrypted and requires a password",
                        file_path=file_path,
                    ))
                
                if not fitz_document.authenticate(password):
                    fitz_document.close()
                    return Failure(PDFPasswordError(
                        message="Invalid password for encrypted PDF",
                        file_path=file_path,
                    ))
            
            file_size = file_path.stat().st_size
            metadata = self._extract_metadata(fitz_document, file_path, file_size)
            
            pdf_document = PDFDocument(
                file_path=file_path,
                file_hash=file_hash,
                document=fitz_document,
                metadata=metadata,
            )
            
            with self._documents_lock:
                while len(self._open_documents) >= self._max_open_documents:
                    self._evict_oldest_document()
                
                self._open_documents[file_hash] = pdf_document
                self._document_access_order.append(file_hash)
            
            logger.info(f"Loaded document: {file_path} ({metadata.page_count} pages)")
            return Success(pdf_document)
            
        except fitz.FileDataError:
            return Failure(PDFCorruptError(
                message=f"PDF file is corrupted: {file_path}",
                file_path=file_path,
            ))
        except Exception as exception:
            return Failure(PDFLoadError(
                message=f"Failed to load PDF: {str(exception)}",
                file_path=file_path,
            ))
    
    def get_document(self, file_hash: str) -> Result[Optional[PDFDocument]]:
        """
        Get a cached document by its hash.
        
        Args:
            file_hash: SHA-256 hash of the file.
        
        Returns:
            Result containing the document or None if not cached.
        """
        with self._documents_lock:
            document = self._open_documents.get(file_hash)
            if document is not None:
                self._update_access_order(file_hash)
            return Success(document)
    
    def close_document(self, file_hash: str) -> Result[bool]:
        """
        Close and remove a document from cache.
        
        Args:
            file_hash: SHA-256 hash of the file.
        
        Returns:
            Result containing True if document was closed.
        """
        with self._documents_lock:
            if file_hash in self._open_documents:
                document = self._open_documents.pop(file_hash)
                document.close()
                if file_hash in self._document_access_order:
                    self._document_access_order.remove(file_hash)
                logger.info(f"Closed document: {document.file_path}")
                return Success(True)
            return Success(False)
    
    def close_all_documents(self) -> Result[int]:
        """
        Close all open documents.
        
        Returns:
            Result containing number of documents closed.
        """
        with self._documents_lock:
            count = len(self._open_documents)
            for document in self._open_documents.values():
                document.close()
            self._open_documents.clear()
            self._document_access_order.clear()
            logger.info(f"Closed all documents (count={count})")
            return Success(count)
    
    def get_open_document_count(self) -> int:
        """Get the number of currently open documents."""
        with self._documents_lock:
            return len(self._open_documents)
    
    def is_valid_pdf(self, file_path: Path) -> Result[bool]:
        """
        Check if a file is a valid PDF without fully loading it.
        
        Args:
            file_path: Path to check.
        
        Returns:
            Result containing True if valid PDF.
        """
        try:
            file_path = Path(file_path).resolve()
            if not file_path.exists():
                return Success(False)
            
            if file_path.suffix.lower() != '.pdf':
                return Success(False)
            
            with open(file_path, 'rb') as file:
                header = file.read(8)
                if not header.startswith(b'%PDF-'):
                    return Success(False)
            
            document = fitz.open(file_path)
            is_valid = len(document) > 0
            document.close()
            
            return Success(is_valid)
            
        except Exception:
            return Success(False)
    
    def render_page_to_pixmap(
        self,
        document: PDFDocument,
        page_number: int,
        scale: float = 1.0,
        rotation: int = 0,
        clip_rect: Optional[Tuple[float, float, float, float]] = None,
    ) -> Result[fitz.Pixmap]:
        """
        Render a page to a pixmap.
        
        Args:
            document: The PDF document.
            page_number: Zero-based page index.
            scale: Zoom scale factor.
            rotation: Additional rotation in degrees (0, 90, 180, 270).
            clip_rect: Optional clip rectangle (x0, y0, x1, y1).
        
        Returns:
            Result containing the rendered pixmap.
        """
        if not document.is_open():
            return Failure(PDFRenderError(
                message="Document is closed",
                file_path=document.file_path,
            ))
        
        if page_number < 0 or page_number >= document.page_count:
            return Failure(PDFRenderError(
                message=f"Page number {page_number} out of range",
                file_path=document.file_path,
                page_number=page_number,
            ))
        
        try:
            page = document.document[page_number]
            
            matrix = fitz.Matrix(scale, scale)
            if rotation:
                matrix = matrix.prerotate(rotation)
            
            clip = None
            if clip_rect is not None:
                clip = fitz.Rect(clip_rect)
            
            pixmap = page.get_pixmap(
                matrix=matrix,
                clip=clip,
                alpha=False,
            )
            
            return Success(pixmap)
            
        except Exception as exception:
            return Failure(PDFRenderError(
                message=f"Failed to render page: {str(exception)}",
                file_path=document.file_path,
                page_number=page_number,
            ))
    
    def render_page_to_image_bytes(
        self,
        document: PDFDocument,
        page_number: int,
        scale: float = 1.0,
        image_format: str = "png",
    ) -> Result[bytes]:
        """
        Render a page to image bytes.
        
        Args:
            document: The PDF document.
            page_number: Zero-based page index.
            scale: Zoom scale factor.
            image_format: Output format (png, jpeg, etc.).
        
        Returns:
            Result containing image bytes.
        """
        pixmap_result = self.render_page_to_pixmap(document, page_number, scale)
        if pixmap_result.is_failure():
            return pixmap_result
        
        try:
            pixmap = pixmap_result.unwrap()
            image_bytes = pixmap.tobytes(image_format)
            return Success(image_bytes)
        except Exception as exception:
            return Failure(PDFRenderError(
                message=f"Failed to convert pixmap to bytes: {str(exception)}",
                file_path=document.file_path,
                page_number=page_number,
            ))
    
    def generate_thumbnail(
        self,
        document: PDFDocument,
        page_number: int = 0,
        max_dimension: int = 200,
    ) -> Result[bytes]:
        """
        Generate a thumbnail for a page.
        
        Args:
            document: The PDF document.
            page_number: Zero-based page index.
            max_dimension: Maximum width or height of thumbnail.
        
        Returns:
            Result containing PNG thumbnail bytes.
        """
        page_info_result = document.get_page_info(page_number)
        if page_info_result.is_failure():
            return page_info_result
        
        page_info = page_info_result.unwrap()
        
        scale = min(
            max_dimension / page_info.width,
            max_dimension / page_info.height,
        )
        
        return self.render_page_to_image_bytes(
            document,
            page_number,
            scale=scale,
            image_format="png",
        )
