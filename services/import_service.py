"""
Import Service

Handles file import operations including:
- Single and batch PDF imports
- File validation and processing
- Metadata extraction
- Duplicate detection
- Import progress tracking
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable, List
from enum import Enum, auto
import threading
import uuid
import time
from concurrent.futures import ThreadPoolExecutor, Future

from PyQt6.QtCore import QObject, pyqtSignal

from core.error_types import (
    Result,
    Success,
    Failure,
    PDFError,
    FileSystemError,
    ValidationError,
)
from core.pdf_engine import PDFEngine
from database.repository import DocumentRepository
from utils.file_ops import (
    calculate_file_hash,
    safe_file_copy,
    is_valid_pdf_file,
    ensure_directory_exists,
    get_unique_filename,
)
from utils.validators import validate_file_path


class ImportStatus(Enum):
    """Status of an import operation."""
    PENDING = auto()
    VALIDATING = auto()
    COPYING = auto()
    EXTRACTING_METADATA = auto()
    CHECKING_DUPLICATES = auto()
    SAVING = auto()
    COMPLETED = auto()
    FAILED = auto()
    SKIPPED = auto()


@dataclass
class ImportResult:
    """Result of importing a single file."""
    
    source_path: Path
    status: ImportStatus
    document_id: Optional[str] = None
    error_message: Optional[str] = None
    is_duplicate: bool = False
    duplicate_document_id: Optional[str] = None
    processing_time_ms: float = 0.0


@dataclass
class BatchImportProgress:
    """Progress information for batch import operations."""
    
    total_files: int = 0
    processed_files: int = 0
    successful_imports: int = 0
    failed_imports: int = 0
    skipped_duplicates: int = 0
    current_file: Optional[str] = None
    current_status: ImportStatus = ImportStatus.PENDING
    is_cancelled: bool = False
    results: List[ImportResult] = field(default_factory=list)
    
    @property
    def progress_percent(self) -> float:
        """Get progress as percentage."""
        if self.total_files == 0:
            return 0.0
        return (self.processed_files / self.total_files) * 100


@dataclass
class ImportOptions:
    """Options for import operations."""
    
    copy_to_library: bool = True
    library_path: Optional[Path] = None
    skip_duplicates: bool = True
    extract_metadata: bool = True
    generate_thumbnails: bool = True
    add_to_collection: Optional[str] = None
    tags: List[str] = field(default_factory=list)


class ImportService(QObject):
    """
    Service for importing PDF files into the application.
    
    Provides single-file and batch import with progress tracking,
    duplicate detection, and metadata extraction.
    
    Signals:
        import_started: Emitted when import begins
        import_progress: Emitted with progress updates (BatchImportProgress)
        import_completed: Emitted when import finishes (BatchImportProgress)
        file_imported: Emitted for each file (ImportResult)
    """
    
    import_started = pyqtSignal()
    import_progress = pyqtSignal(object)  # BatchImportProgress
    import_completed = pyqtSignal(object)  # BatchImportProgress
    file_imported = pyqtSignal(object)  # ImportResult
    
    def __init__(
        self,
        document_repository: DocumentRepository,
        library_path: Optional[Path] = None,
        max_workers: int = 4,
    ):
        super().__init__()
        
        self._document_repo = document_repository
        self._default_library_path = library_path
        self._max_workers = max_workers
        self._pdf_engine = PDFEngine()
        
        self._executor: Optional[ThreadPoolExecutor] = None
        self._current_import: Optional[Future] = None
        self._cancel_requested = False
        self._lock = threading.Lock()
    
    def import_file(
        self,
        file_path: Path | str,
        options: Optional[ImportOptions] = None,
    ) -> Result[ImportResult]:
        """
        Import a single PDF file.
        
        Args:
            file_path: Path to the PDF file.
            options: Import options.
        
        Returns:
            Result containing ImportResult with details.
        """
        options = options or ImportOptions()
        file_path = Path(file_path)
        start_time = time.time()
        
        # Validate file path
        validation_result = validate_file_path(
            file_path,
            must_exist=True,
            allowed_extensions=['.pdf'],
        )
        if validation_result.is_failure:
            return Success(ImportResult(
                source_path=file_path,
                status=ImportStatus.FAILED,
                error_message=str(validation_result.error),
                processing_time_ms=(time.time() - start_time) * 1000,
            ))
        
        # Validate PDF structure
        is_valid = is_valid_pdf_file(file_path)
        if is_valid.is_failure or not is_valid.value:
            return Success(ImportResult(
                source_path=file_path,
                status=ImportStatus.FAILED,
                error_message="Invalid or corrupted PDF file",
                processing_time_ms=(time.time() - start_time) * 1000,
            ))
        
        # Calculate file hash for duplicate detection
        hash_result = calculate_file_hash(file_path)
        if hash_result.is_failure:
            return Success(ImportResult(
                source_path=file_path,
                status=ImportStatus.FAILED,
                error_message=f"Failed to calculate file hash: {hash_result.error}",
                processing_time_ms=(time.time() - start_time) * 1000,
            ))
        
        file_hash = hash_result.value
        
        # Check for duplicates
        if options.skip_duplicates:
            existing_doc = self._document_repo.get_by_hash(file_hash)
            if existing_doc.is_success and existing_doc.value:
                return Success(ImportResult(
                    source_path=file_path,
                    status=ImportStatus.SKIPPED,
                    is_duplicate=True,
                    duplicate_document_id=existing_doc.value.id,
                    processing_time_ms=(time.time() - start_time) * 1000,
                ))
        
        # Determine destination path
        destination_path = file_path
        if options.copy_to_library:
            library_path = options.library_path or self._default_library_path
            if library_path:
                ensure_directory_exists(library_path)
                dest_name = get_unique_filename(library_path, file_path.name)
                destination_path = library_path / dest_name.value if dest_name.is_success else library_path / file_path.name
                
                copy_result = safe_file_copy(file_path, destination_path)
                if copy_result.is_failure:
                    return Success(ImportResult(
                        source_path=file_path,
                        status=ImportStatus.FAILED,
                        error_message=f"Failed to copy file: {copy_result.error}",
                        processing_time_ms=(time.time() - start_time) * 1000,
                    ))
        
        # Extract metadata
        metadata = {}
        if options.extract_metadata:
            doc_result = self._pdf_engine.load_document(destination_path)
            if doc_result.is_success:
                pdf_doc = doc_result.value
                pdf_metadata = pdf_doc.get_metadata()
                if pdf_metadata.is_success:
                    meta = pdf_metadata.value
                    metadata = {
                        "title": meta.title,
                        "author": meta.author,
                        "subject": meta.subject,
                        "keywords": meta.keywords,
                        "creator": meta.creator,
                        "producer": meta.producer,
                        "page_count": meta.page_count,
                    }
                pdf_doc.close()
        
        # Generate document ID
        document_id = str(uuid.uuid4())
        
        # Create document record
        from database.schema import DocumentRecord
        
        doc_record = DocumentRecord(
            id=document_id,
            file_path=str(destination_path),
            file_hash=file_hash,
            title=metadata.get("title") or file_path.stem,
            author=metadata.get("author"),
            page_count=metadata.get("page_count", 0),
            file_size=destination_path.stat().st_size,
        )
        
        save_result = self._document_repo.create(doc_record)
        if save_result.is_failure:
            return Success(ImportResult(
                source_path=file_path,
                status=ImportStatus.FAILED,
                error_message=f"Failed to save document: {save_result.error}",
                processing_time_ms=(time.time() - start_time) * 1000,
            ))
        
        return Success(ImportResult(
            source_path=file_path,
            status=ImportStatus.COMPLETED,
            document_id=document_id,
            processing_time_ms=(time.time() - start_time) * 1000,
        ))
    
    def import_files_batch(
        self,
        file_paths: List[Path | str],
        options: Optional[ImportOptions] = None,
        progress_callback: Optional[Callable[[BatchImportProgress], None]] = None,
    ) -> Result[BatchImportProgress]:
        """
        Import multiple PDF files.
        
        Args:
            file_paths: List of file paths to import.
            options: Import options.
            progress_callback: Optional callback for progress updates.
        
        Returns:
            Result containing BatchImportProgress with overall results.
        """
        options = options or ImportOptions()
        
        progress = BatchImportProgress(
            total_files=len(file_paths),
        )
        
        self.import_started.emit()
        
        for i, file_path in enumerate(file_paths):
            if self._cancel_requested:
                progress.is_cancelled = True
                break
            
            file_path = Path(file_path)
            progress.current_file = file_path.name
            progress.current_status = ImportStatus.VALIDATING
            
            if progress_callback:
                progress_callback(progress)
            self.import_progress.emit(progress)
            
            # Import the file
            result = self.import_file(file_path, options)
            
            if result.is_success:
                import_result = result.value
                progress.results.append(import_result)
                
                if import_result.status == ImportStatus.COMPLETED:
                    progress.successful_imports += 1
                elif import_result.status == ImportStatus.SKIPPED:
                    progress.skipped_duplicates += 1
                else:
                    progress.failed_imports += 1
                
                self.file_imported.emit(import_result)
            else:
                progress.failed_imports += 1
                progress.results.append(ImportResult(
                    source_path=file_path,
                    status=ImportStatus.FAILED,
                    error_message=str(result.error),
                ))
            
            progress.processed_files = i + 1
            
            if progress_callback:
                progress_callback(progress)
            self.import_progress.emit(progress)
        
        progress.current_status = ImportStatus.COMPLETED
        self.import_completed.emit(progress)
        
        return Success(progress)
    
    def import_files_async(
        self,
        file_paths: List[Path | str],
        options: Optional[ImportOptions] = None,
    ) -> None:
        """
        Import files asynchronously in background.
        
        Progress updates are sent via signals.
        
        Args:
            file_paths: List of file paths to import.
            options: Import options.
        """
        with self._lock:
            if self._executor is None:
                self._executor = ThreadPoolExecutor(max_workers=1)
            
            self._cancel_requested = False
            self._current_import = self._executor.submit(
                self.import_files_batch,
                file_paths,
                options,
            )
    
    def cancel_import(self) -> None:
        """Request cancellation of current import operation."""
        self._cancel_requested = True
    
    def is_importing(self) -> bool:
        """Check if an import is currently in progress."""
        with self._lock:
            if self._current_import is None:
                return False
            return not self._current_import.done()
    
    def import_from_directory(
        self,
        directory: Path | str,
        options: Optional[ImportOptions] = None,
        recursive: bool = True,
    ) -> Result[BatchImportProgress]:
        """
        Import all PDF files from a directory.
        
        Args:
            directory: Directory to scan for PDFs.
            options: Import options.
            recursive: Whether to scan subdirectories.
        
        Returns:
            Result containing BatchImportProgress.
        """
        directory = Path(directory)
        
        if not directory.exists():
            return Failure(FileSystemError(
                message="Directory does not exist",
                path=str(directory),
                operation="import",
            ))
        
        if not directory.is_dir():
            return Failure(FileSystemError(
                message="Path is not a directory",
                path=str(directory),
                operation="import",
            ))
        
        # Find all PDF files
        if recursive:
            pdf_files = list(directory.rglob("*.pdf"))
        else:
            pdf_files = list(directory.glob("*.pdf"))
        
        if not pdf_files:
            return Success(BatchImportProgress(
                total_files=0,
                current_status=ImportStatus.COMPLETED,
            ))
        
        return self.import_files_batch(pdf_files, options)
    
    def validate_files(
        self,
        file_paths: List[Path | str],
    ) -> List[tuple[Path, bool, Optional[str]]]:
        """
        Validate multiple files without importing.
        
        Args:
            file_paths: List of file paths to validate.
        
        Returns:
            List of tuples: (path, is_valid, error_message)
        """
        results = []
        
        for file_path in file_paths:
            file_path = Path(file_path)
            
            # Check if file exists
            if not file_path.exists():
                results.append((file_path, False, "File does not exist"))
                continue
            
            # Check extension
            if file_path.suffix.lower() != '.pdf':
                results.append((file_path, False, "Not a PDF file"))
                continue
            
            # Validate PDF structure
            is_valid = is_valid_pdf_file(file_path)
            if is_valid.is_failure or not is_valid.value:
                results.append((file_path, False, "Invalid or corrupted PDF"))
                continue
            
            results.append((file_path, True, None))
        
        return results
    
    def check_duplicates(
        self,
        file_paths: List[Path | str],
    ) -> dict[str, Optional[str]]:
        """
        Check for duplicate files.
        
        Args:
            file_paths: List of file paths to check.
        
        Returns:
            Dictionary mapping file path to duplicate document ID (or None).
        """
        results = {}
        
        for file_path in file_paths:
            file_path = Path(file_path)
            
            hash_result = calculate_file_hash(file_path)
            if hash_result.is_failure:
                results[str(file_path)] = None
                continue
            
            existing_doc = self._document_repo.get_by_hash(hash_result.value)
            if existing_doc.is_success and existing_doc.value:
                results[str(file_path)] = existing_doc.value.id
            else:
                results[str(file_path)] = None
        
        return results
    
    def shutdown(self) -> None:
        """Shutdown the import service and cleanup resources."""
        self._cancel_requested = True
        
        with self._lock:
            if self._executor:
                self._executor.shutdown(wait=False)
                self._executor = None
