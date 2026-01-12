from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import TypeVar, Generic, Callable, Optional, Union
from pathlib import Path
import traceback
import logging

T = TypeVar("T")
E = TypeVar("E", bound="AppError")


class ErrorSeverity(Enum):
    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()


@dataclass(frozen=True)
class AppError(ABC):
    """Base class for all application errors with rich context."""
    
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    severity: ErrorSeverity = ErrorSeverity.ERROR
    source_file: Optional[str] = None
    source_line: Optional[int] = None
    stack_trace: Optional[str] = None
    
    @abstractmethod
    def error_code(self) -> str:
        """Return unique error code for this error type."""
        pass
    
    def with_context(self, **kwargs) -> AppError:
        """Create new error with additional context."""
        return self.__class__(
            message=f"{self.message} | Context: {kwargs}",
            timestamp=self.timestamp,
            severity=self.severity,
            source_file=self.source_file,
            source_line=self.source_line,
            stack_trace=self.stack_trace,
        )
    
    def log(self, logger: logging.Logger) -> None:
        """Log this error with appropriate severity level."""
        log_methods = {
            ErrorSeverity.DEBUG: logger.debug,
            ErrorSeverity.INFO: logger.info,
            ErrorSeverity.WARNING: logger.warning,
            ErrorSeverity.ERROR: logger.error,
            ErrorSeverity.CRITICAL: logger.critical,
        }
        log_method = log_methods.get(self.severity, logger.error)
        log_message = f"[{self.error_code()}] {self.message}"
        if self.source_file:
            log_message += f" at {self.source_file}:{self.source_line}"
        log_method(log_message)


@dataclass(frozen=True)
class PDFError(AppError):
    """Errors related to PDF operations."""
    
    file_path: Optional[Path] = None
    page_number: Optional[int] = None
    
    def error_code(self) -> str:
        return "PDF_ERR"


@dataclass(frozen=True)
class PDFLoadError(PDFError):
    """Error when loading a PDF file fails."""
    
    def error_code(self) -> str:
        return "PDF_LOAD_ERR"


@dataclass(frozen=True)
class PDFRenderError(PDFError):
    """Error when rendering a PDF page fails."""
    
    def error_code(self) -> str:
        return "PDF_RENDER_ERR"


@dataclass(frozen=True)
class PDFCorruptError(PDFError):
    """Error when PDF file is corrupted."""
    
    def error_code(self) -> str:
        return "PDF_CORRUPT_ERR"


@dataclass(frozen=True)
class PDFPasswordError(PDFError):
    """Error when PDF requires password."""
    
    def error_code(self) -> str:
        return "PDF_PASSWORD_ERR"


@dataclass(frozen=True)
class RenderError(AppError):
    """Errors related to rendering operations."""
    
    render_target: Optional[str] = None
    
    def error_code(self) -> str:
        return "RENDER_ERR"


@dataclass(frozen=True)
class CacheError(AppError):
    """Errors related to cache operations."""
    
    cache_key: Optional[str] = None
    
    def error_code(self) -> str:
        return "CACHE_ERR"


@dataclass(frozen=True)
class DatabaseError(AppError):
    """Errors related to database operations."""
    
    table_name: Optional[str] = None
    operation: Optional[str] = None
    
    def error_code(self) -> str:
        return "DB_ERR"


@dataclass(frozen=True)
class DatabaseConnectionError(DatabaseError):
    """Error when database connection fails."""
    
    def error_code(self) -> str:
        return "DB_CONN_ERR"


@dataclass(frozen=True)
class DatabaseQueryError(DatabaseError):
    """Error when database query fails."""
    
    query: Optional[str] = None
    
    def error_code(self) -> str:
        return "DB_QUERY_ERR"


@dataclass(frozen=True)
class ValidationError(AppError):
    """Errors related to input validation."""
    
    field_name: Optional[str] = None
    invalid_value: Optional[str] = None
    
    def error_code(self) -> str:
        return "VALIDATION_ERR"


@dataclass(frozen=True)
class FileSystemError(AppError):
    """Errors related to file system operations."""
    
    path: Optional[Path] = None
    operation: Optional[str] = None
    
    def error_code(self) -> str:
        return "FS_ERR"


@dataclass(frozen=True)
class FileNotFoundError(FileSystemError):
    """Error when file is not found."""
    
    def error_code(self) -> str:
        return "FS_NOT_FOUND_ERR"


@dataclass(frozen=True)
class FilePermissionError(FileSystemError):
    """Error when file permission denied."""
    
    def error_code(self) -> str:
        return "FS_PERMISSION_ERR"


@dataclass(frozen=True)
class AnnotationError(AppError):
    """Errors related to annotation operations."""
    
    annotation_id: Optional[str] = None
    annotation_type: Optional[str] = None
    
    def error_code(self) -> str:
        return "ANNOTATION_ERR"


@dataclass(frozen=True)
class SerializationError(AppError):
    """Errors related to serialization/deserialization."""
    
    data_type: Optional[str] = None
    
    def error_code(self) -> str:
        return "SERIALIZATION_ERR"


@dataclass(frozen=True)
class ExportError(AppError):
    """Errors related to export operations."""
    
    export_format: Optional[str] = None
    destination: Optional[Path] = None
    
    def error_code(self) -> str:
        return "EXPORT_ERR"


@dataclass(frozen=True)
class SearchError(AppError):
    """Errors related to search operations."""
    
    search_query: Optional[str] = None
    search_scope: Optional[str] = None
    
    def error_code(self) -> str:
        return "SEARCH_ERR"


@dataclass(frozen=True)
class ImportError(AppError):
    """Errors related to import operations."""
    
    source_path: Optional[Path] = None
    import_type: Optional[str] = None
    
    def error_code(self) -> str:
        return "IMPORT_ERR"


class Result(Generic[T], ABC):
    """
    A Result type representing either success or failure.
    Inspired by Rust's Result type for explicit error handling.
    """
    
    @abstractmethod
    def is_success(self) -> bool:
        """Check if this result represents success."""
        pass
    
    @abstractmethod
    def is_failure(self) -> bool:
        """Check if this result represents failure."""
        pass
    
    @abstractmethod
    def unwrap(self) -> T:
        """
        Get the success value.
        Raises RuntimeError if this is a failure.
        """
        pass
    
    @abstractmethod
    def unwrap_or(self, default: T) -> T:
        """Get the success value or return default if failure."""
        pass
    
    @abstractmethod
    def unwrap_or_else(self, default_factory: Callable[[], T]) -> T:
        """Get the success value or compute default if failure."""
        pass
    
    @abstractmethod
    def map(self, transform: Callable[[T], "U"]) -> "Result[U]":
        """Transform the success value if present."""
        pass
    
    @abstractmethod
    def flat_map(self, transform: Callable[[T], "Result[U]"]) -> "Result[U]":
        """Transform the success value with a function that returns Result."""
        pass
    
    @abstractmethod
    def map_error(self, transform: Callable[[AppError], AppError]) -> "Result[T]":
        """Transform the error if present."""
        pass
    
    @abstractmethod
    def get_error(self) -> Optional[AppError]:
        """Get the error if this is a failure, None otherwise."""
        pass
    
    @abstractmethod
    def on_success(self, action: Callable[[T], None]) -> "Result[T]":
        """Execute action if success, return self for chaining."""
        pass
    
    @abstractmethod
    def on_failure(self, action: Callable[[AppError], None]) -> "Result[T]":
        """Execute action if failure, return self for chaining."""
        pass


U = TypeVar("U")


@dataclass
class Success(Result[T]):
    """Represents a successful result containing a value."""
    
    value: T
    
    def is_success(self) -> bool:
        return True
    
    def is_failure(self) -> bool:
        return False
    
    def unwrap(self) -> T:
        return self.value
    
    def unwrap_or(self, default: T) -> T:
        return self.value
    
    def unwrap_or_else(self, default_factory: Callable[[], T]) -> T:
        return self.value
    
    def map(self, transform: Callable[[T], U]) -> Result[U]:
        return Success(transform(self.value))
    
    def flat_map(self, transform: Callable[[T], Result[U]]) -> Result[U]:
        return transform(self.value)
    
    def map_error(self, transform: Callable[[AppError], AppError]) -> Result[T]:
        return self
    
    def get_error(self) -> Optional[AppError]:
        return None
    
    def on_success(self, action: Callable[[T], None]) -> Result[T]:
        action(self.value)
        return self
    
    def on_failure(self, action: Callable[[AppError], None]) -> Result[T]:
        return self


@dataclass
class Failure(Result[T]):
    """Represents a failed result containing an error."""
    
    error: AppError
    
    def is_success(self) -> bool:
        return False
    
    def is_failure(self) -> bool:
        return True
    
    def unwrap(self) -> T:
        raise RuntimeError(f"Attempted to unwrap a Failure: {self.error.message}")
    
    def unwrap_or(self, default: T) -> T:
        return default
    
    def unwrap_or_else(self, default_factory: Callable[[], T]) -> T:
        return default_factory()
    
    def map(self, transform: Callable[[T], U]) -> Result[U]:
        return Failure(self.error)
    
    def flat_map(self, transform: Callable[[T], Result[U]]) -> Result[U]:
        return Failure(self.error)
    
    def map_error(self, transform: Callable[[AppError], AppError]) -> Result[T]:
        return Failure(transform(self.error))
    
    def get_error(self) -> Optional[AppError]:
        return self.error
    
    def on_success(self, action: Callable[[T], None]) -> Result[T]:
        return self
    
    def on_failure(self, action: Callable[[AppError], None]) -> Result[T]:
        action(self.error)
        return self


def capture_exception(
    error_class: type[AppError],
    message: str,
    **extra_fields
) -> AppError:
    """
    Capture current exception context and create an error with stack trace.
    """
    stack = traceback.format_exc()
    frame = traceback.extract_stack()[-2] if len(traceback.extract_stack()) >= 2 else None
    
    return error_class(
        message=message,
        stack_trace=stack,
        source_file=frame.filename if frame else None,
        source_line=frame.lineno if frame else None,
        **extra_fields
    )


def try_execute(
    operation: Callable[[], T],
    error_class: type[AppError],
    error_message: str,
    **error_fields
) -> Result[T]:
    """
    Execute an operation and wrap exceptions in a Result.
    """
    try:
        return Success(operation())
    except Exception as exception:
        return Failure(capture_exception(
            error_class,
            f"{error_message}: {str(exception)}",
            **error_fields
        ))


def combine_results(results: list[Result[T]]) -> Result[list[T]]:
    """
    Combine multiple results into a single result containing all values.
    Returns Failure with first error encountered if any result is failure.
    """
    values: list[T] = []
    for result in results:
        if result.is_failure():
            return Failure(result.get_error())
        values.append(result.unwrap())
    return Success(values)


def sequence_results(results: list[Result[T]]) -> Result[list[T]]:
    """
    Sequence multiple results, collecting all errors if any fail.
    Returns Success only if all results succeed.
    """
    successes: list[T] = []
    failures: list[AppError] = []
    
    for result in results:
        if result.is_success():
            successes.append(result.unwrap())
        else:
            failures.append(result.get_error())
    
    if failures:
        combined_message = "; ".join(error.message for error in failures)
        return Failure(AppError(message=f"Multiple errors: {combined_message}"))
    
    return Success(successes)
