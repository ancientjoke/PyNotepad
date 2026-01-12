from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Optional, Dict, List, Callable, Any, TYPE_CHECKING
from concurrent.futures import ThreadPoolExecutor, Future
import threading
import logging
import uuid

from PyQt6.QtCore import QObject, pyqtSignal

from core.error_types import (
    Result,
    Success,
    Failure,
    PDFError,
    PDFLoadError,
    FileSystemError,
)
from core.pdf_engine import PDFEngine, PDFDocument, PDFMetadata
from core.render_engine import RenderEngine

if TYPE_CHECKING:
    from database.repository import DocumentRepository, AnnotationRepository
    from database.schema import DocumentRecord

logger = logging.getLogger(__name__)


class DocumentState(Enum):
    """Document lifecycle states."""
    UNLOADED = auto()
    LOADING = auto()
    LOADED = auto()
    ERROR = auto()
    CLOSING = auto()
    CLOSED = auto()


@dataclass
class DocumentContext:
    """Runtime context for an open document."""
    
    document_id: Optional[int]
    file_path: Path
    file_hash: str
    pdf_document: Optional[PDFDocument]
    state: DocumentState
    error_message: Optional[str] = None
    
    current_page: int = 0
    zoom_level: float = 1.0
    rotation: int = 0
    scroll_position_x: float = 0.0
    scroll_position_y: float = 0.0
    
    annotation_branch: str = "main"
    
    is_modified: bool = False
    
    opened_at: datetime = field(default_factory=datetime.now)
    
    @property
    def is_ready(self) -> bool:
        """Check if document is ready for use."""
        return self.state == DocumentState.LOADED and self.pdf_document is not None


class DocumentEventType(Enum):
    """Types of document events."""
    DOCUMENT_LOADING = auto()
    DOCUMENT_LOADED = auto()
    DOCUMENT_LOAD_ERROR = auto()
    DOCUMENT_CLOSING = auto()
    DOCUMENT_CLOSED = auto()
    PAGE_CHANGED = auto()
    ZOOM_CHANGED = auto()
    ROTATION_CHANGED = auto()
    ANNOTATIONS_CHANGED = auto()
    DOCUMENT_MODIFIED = auto()


@dataclass(frozen=True)
class DocumentEvent:
    """Event emitted when document state changes."""
    
    event_type: DocumentEventType
    document_hash: str
    file_path: Path
    data: Optional[Dict[str, Any]] = None


class DocumentManager(QObject):
    """
    Manages the lifecycle of PDF documents including loading, caching, 
    and state persistence. Acts as a facade over PDFEngine and RenderEngine.
    """
    
    document_event = pyqtSignal(object)
    
    MAX_RECENT_FILES = 20
    
    def __init__(
        self,
        pdf_engine: Optional[PDFEngine] = None,
        render_engine: Optional[RenderEngine] = None,
        thread_pool_size: int = 4,
    ):
        super().__init__()
        
        self._pdf_engine = pdf_engine or PDFEngine()
        self._render_engine = render_engine or RenderEngine(self._pdf_engine)
        
        self._open_documents: Dict[str, DocumentContext] = {}
        self._documents_lock = threading.RLock()
        
        self._thread_pool = ThreadPoolExecutor(
            max_workers=thread_pool_size,
            thread_name_prefix="DocumentManager",
        )
        
        # Lazy import to avoid circular dependency
        from database.repository import DocumentRepository, AnnotationRepository
        self._document_repository = DocumentRepository()
        self._annotation_repository = AnnotationRepository()
        
        self._active_document_hash: Optional[str] = None
        
        logger.info(f"DocumentManager initialized with thread_pool_size={thread_pool_size}")
    
    def _emit_event(
        self,
        event_type: DocumentEventType,
        document_hash: str,
        file_path: Path,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit a document event signal."""
        event = DocumentEvent(
            event_type=event_type,
            document_hash=document_hash,
            file_path=file_path,
            data=data,
        )
        self.document_event.emit(event)
        logger.debug(f"Emitted event: {event_type.name} for {file_path}")
    
    def _get_or_create_document_record(
        self,
        pdf_document: PDFDocument,
    ) -> Result[DocumentRecord]:
        """Get existing document record or create a new one."""
        from database.schema import DocumentRecord  # Lazy import to avoid circular dependency
        
        existing_result = self._document_repository.get_by_file_hash(
            pdf_document.file_hash
        )
        
        if existing_result.is_failure():
            return existing_result
        
        existing = existing_result.unwrap()
        if existing is not None:
            if str(existing.file_path) != str(pdf_document.file_path):
                existing.file_path = str(pdf_document.file_path)
                return self._document_repository.update(existing)
            return Success(existing)
        
        metadata = pdf_document.metadata
        
        new_record = DocumentRecord(
            file_path=str(pdf_document.file_path),
            file_name=pdf_document.file_path.name,
            file_hash=pdf_document.file_hash,
            file_size_bytes=metadata.file_size_bytes,
            title=metadata.title,
            author=metadata.author,
            subject=metadata.subject,
            keywords=metadata.keywords,
            creator=metadata.creator,
            producer=metadata.producer,
            page_count=metadata.page_count,
            creation_date=metadata.creation_date,
            modification_date=metadata.modification_date,
        )
        
        return self._document_repository.create(new_record)
    
    def open_document(
        self,
        file_path: Path,
        password: Optional[str] = None,
    ) -> Result[DocumentContext]:
        """
        Open a PDF document synchronously.
        
        Args:
            file_path: Path to the PDF file.
            password: Optional password for encrypted PDFs.
        
        Returns:
            Result containing DocumentContext or error.
        """
        file_path = Path(file_path).resolve()
        
        load_result = self._pdf_engine.load_document(file_path, password)
        
        if load_result.is_failure():
            context = DocumentContext(
                document_id=None,
                file_path=file_path,
                file_hash="",
                pdf_document=None,
                state=DocumentState.ERROR,
                error_message=load_result.get_error().message,
            )
            
            self._emit_event(
                DocumentEventType.DOCUMENT_LOAD_ERROR,
                "",
                file_path,
                {"error": load_result.get_error().message},
            )
            
            return Failure(load_result.get_error())
        
        pdf_document = load_result.unwrap()
        
        with self._documents_lock:
            if pdf_document.file_hash in self._open_documents:
                existing_context = self._open_documents[pdf_document.file_hash]
                if existing_context.is_ready:
                    self._active_document_hash = pdf_document.file_hash
                    return Success(existing_context)
        
        record_result = self._get_or_create_document_record(pdf_document)
        
        document_id = None
        if record_result.is_success():
            record = record_result.unwrap()
            document_id = record.id
            self._document_repository.update_last_opened(document_id)
        
        context = DocumentContext(
            document_id=document_id,
            file_path=file_path,
            file_hash=pdf_document.file_hash,
            pdf_document=pdf_document,
            state=DocumentState.LOADED,
        )
        
        if record_result.is_success():
            record = record_result.unwrap()
            context.current_page = record.last_viewed_page
            context.zoom_level = record.last_zoom_level
            context.scroll_position_x = record.last_scroll_position_x
            context.scroll_position_y = record.last_scroll_position_y
        
        with self._documents_lock:
            self._open_documents[pdf_document.file_hash] = context
            self._active_document_hash = pdf_document.file_hash
        
        self._emit_event(
            DocumentEventType.DOCUMENT_LOADED,
            pdf_document.file_hash,
            file_path,
            {"page_count": pdf_document.metadata.page_count},
        )
        
        logger.info(f"Opened document: {file_path}")
        return Success(context)
    
    def open_document_async(
        self,
        file_path: Path,
        password: Optional[str] = None,
        callback: Optional[Callable[[Result[DocumentContext]], None]] = None,
    ) -> Future:
        """
        Open a PDF document asynchronously.
        
        Args:
            file_path: Path to the PDF file.
            password: Optional password for encrypted PDFs.
            callback: Optional callback to invoke with result.
        
        Returns:
            Future representing the async operation.
        """
        file_path = Path(file_path).resolve()
        
        temp_context = DocumentContext(
            document_id=None,
            file_path=file_path,
            file_hash=str(uuid.uuid4()),
            pdf_document=None,
            state=DocumentState.LOADING,
        )
        
        self._emit_event(
            DocumentEventType.DOCUMENT_LOADING,
            temp_context.file_hash,
            file_path,
        )
        
        def load_task() -> Result[DocumentContext]:
            result = self.open_document(file_path, password)
            if callback is not None:
                callback(result)
            return result
        
        return self._thread_pool.submit(load_task)
    
    def close_document(self, document_hash: str) -> Result[bool]:
        """
        Close an open document.
        
        Args:
            document_hash: Hash of the document to close.
        
        Returns:
            Result containing True if closed successfully.
        """
        with self._documents_lock:
            if document_hash not in self._open_documents:
                return Success(False)
            
            context = self._open_documents[document_hash]
            context.state = DocumentState.CLOSING
            
            self._emit_event(
                DocumentEventType.DOCUMENT_CLOSING,
                document_hash,
                context.file_path,
            )
            
            if context.document_id is not None:
                self._document_repository.update_view_state(
                    context.document_id,
                    context.current_page,
                    context.zoom_level,
                    context.scroll_position_x,
                    context.scroll_position_y,
                )
            
            self._pdf_engine.close_document(document_hash)
            self._render_engine.invalidate_document_cache(document_hash)
            
            del self._open_documents[document_hash]
            
            if self._active_document_hash == document_hash:
                self._active_document_hash = next(
                    iter(self._open_documents.keys()), None
                )
            
            context.state = DocumentState.CLOSED
            
            self._emit_event(
                DocumentEventType.DOCUMENT_CLOSED,
                document_hash,
                context.file_path,
            )
            
            logger.info(f"Closed document: {context.file_path}")
            return Success(True)
    
    def close_all_documents(self) -> Result[int]:
        """
        Close all open documents.
        
        Returns:
            Result containing number of documents closed.
        """
        with self._documents_lock:
            document_hashes = list(self._open_documents.keys())
        
        closed_count = 0
        for doc_hash in document_hashes:
            result = self.close_document(doc_hash)
            if result.is_success() and result.unwrap():
                closed_count += 1
        
        return Success(closed_count)
    
    def get_document_context(
        self,
        document_hash: str,
    ) -> Result[Optional[DocumentContext]]:
        """
        Get the context for an open document.
        
        Args:
            document_hash: Hash of the document.
        
        Returns:
            Result containing DocumentContext or None.
        """
        with self._documents_lock:
            context = self._open_documents.get(document_hash)
            return Success(context)
    
    def get_active_document(self) -> Result[Optional[DocumentContext]]:
        """
        Get the currently active document context.
        
        Returns:
            Result containing the active DocumentContext or None.
        """
        if self._active_document_hash is None:
            return Success(None)
        return self.get_document_context(self._active_document_hash)
    
    def set_active_document(self, document_hash: str) -> Result[bool]:
        """
        Set the active document.
        
        Args:
            document_hash: Hash of the document to activate.
        
        Returns:
            Result containing True if successful.
        """
        with self._documents_lock:
            if document_hash not in self._open_documents:
                return Success(False)
            self._active_document_hash = document_hash
            return Success(True)
    
    def get_all_open_documents(self) -> List[DocumentContext]:
        """Get all currently open documents."""
        with self._documents_lock:
            return list(self._open_documents.values())
    
    def set_current_page(
        self,
        document_hash: str,
        page_number: int,
    ) -> Result[bool]:
        """
        Set the current page for a document.
        
        Args:
            document_hash: Hash of the document.
            page_number: Zero-based page number.
        
        Returns:
            Result containing True if successful.
        """
        with self._documents_lock:
            context = self._open_documents.get(document_hash)
            if context is None or not context.is_ready:
                return Success(False)
            
            page_count = context.pdf_document.page_count
            if page_number < 0 or page_number >= page_count:
                return Success(False)
            
            context.current_page = page_number
            context.is_modified = True
            
            self._render_engine.preload_pages(
                context.pdf_document,
                page_number,
                context.zoom_level,
                context.rotation,
            )
            
            self._emit_event(
                DocumentEventType.PAGE_CHANGED,
                document_hash,
                context.file_path,
                {"page_number": page_number, "page_count": page_count},
            )
            
            return Success(True)
    
    def set_zoom_level(
        self,
        document_hash: str,
        zoom_level: float,
    ) -> Result[bool]:
        """
        Set the zoom level for a document.
        
        Args:
            document_hash: Hash of the document.
            zoom_level: Zoom factor (0.1 to 5.0).
        
        Returns:
            Result containing True if successful.
        """
        zoom_level = max(0.1, min(5.0, zoom_level))
        
        with self._documents_lock:
            context = self._open_documents.get(document_hash)
            if context is None or not context.is_ready:
                return Success(False)
            
            context.zoom_level = zoom_level
            context.is_modified = True
            
            self._emit_event(
                DocumentEventType.ZOOM_CHANGED,
                document_hash,
                context.file_path,
                {"zoom_level": zoom_level},
            )
            
            return Success(True)
    
    def set_rotation(
        self,
        document_hash: str,
        rotation: int,
    ) -> Result[bool]:
        """
        Set the rotation for a document.
        
        Args:
            document_hash: Hash of the document.
            rotation: Rotation in degrees (0, 90, 180, 270).
        
        Returns:
            Result containing True if successful.
        """
        rotation = rotation % 360
        if rotation not in (0, 90, 180, 270):
            rotation = 0
        
        with self._documents_lock:
            context = self._open_documents.get(document_hash)
            if context is None or not context.is_ready:
                return Success(False)
            
            context.rotation = rotation
            context.is_modified = True
            
            self._render_engine.invalidate_document_cache(document_hash)
            
            self._emit_event(
                DocumentEventType.ROTATION_CHANGED,
                document_hash,
                context.file_path,
                {"rotation": rotation},
            )
            
            return Success(True)
    
    def set_scroll_position(
        self,
        document_hash: str,
        scroll_x: float,
        scroll_y: float,
    ) -> Result[bool]:
        """
        Set the scroll position for a document.
        
        Args:
            document_hash: Hash of the document.
            scroll_x: Horizontal scroll position.
            scroll_y: Vertical scroll position.
        
        Returns:
            Result containing True if successful.
        """
        with self._documents_lock:
            context = self._open_documents.get(document_hash)
            if context is None:
                return Success(False)
            
            context.scroll_position_x = scroll_x
            context.scroll_position_y = scroll_y
            context.is_modified = True
            
            return Success(True)
    
    def get_recent_documents(self, limit: int = 10) -> Result[List[DocumentRecord]]:
        """
        Get recently opened documents from the database.
        
        Args:
            limit: Maximum number of documents to return.
        
        Returns:
            Result containing list of DocumentRecords.
        """
        return self._document_repository.get_recent(limit)
    
    def search_documents(self, search_term: str) -> Result[List[DocumentRecord]]:
        """
        Search documents by name.
        
        Args:
            search_term: Term to search for.
        
        Returns:
            Result containing matching DocumentRecords.
        """
        return self._document_repository.search_by_name(search_term)
    
    def get_document_by_id(
        self,
        document_id: int,
    ) -> Result[Optional[DocumentRecord]]:
        """
        Get a document record by ID.
        
        Args:
            document_id: Database ID of the document.
        
        Returns:
            Result containing DocumentRecord or None.
        """
        return self._document_repository.get_by_id(document_id)
    
    def toggle_favorite(self, document_id: int) -> Result[DocumentRecord]:
        """
        Toggle the favorite status of a document.
        
        Args:
            document_id: Database ID of the document.
        
        Returns:
            Result containing updated DocumentRecord.
        """
        return self._document_repository.toggle_favorite(document_id)
    
    def delete_document_from_library(self, document_id: int) -> Result[bool]:
        """
        Delete a document from the library (not the file).
        
        Args:
            document_id: Database ID of the document.
        
        Returns:
            Result containing True if deleted.
        """
        self._annotation_repository.delete_for_document(document_id)
        return self._document_repository.delete(document_id)
    
    @property
    def pdf_engine(self) -> PDFEngine:
        """Get the PDF engine instance."""
        return self._pdf_engine
    
    @property
    def render_engine(self) -> RenderEngine:
        """Get the render engine instance."""
        return self._render_engine
    
    def shutdown(self) -> None:
        """Shutdown the document manager and release resources."""
        logger.info("Shutting down DocumentManager...")
        
        self.close_all_documents()
        
        self._thread_pool.shutdown(wait=True)
        
        self._pdf_engine.close_all_documents()
        self._render_engine.clear_cache()
        
        logger.info("DocumentManager shutdown complete")
