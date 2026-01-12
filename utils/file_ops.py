from __future__ import annotations
from pathlib import Path
from typing import Optional, Tuple
import hashlib
import shutil
import os
import logging

from core.error_types import (
    Result,
    Success,
    Failure,
    FileSystemError,
    FileNotFoundError as AppFileNotFoundError,
    FilePermissionError as AppFilePermissionError,
)

logger = logging.getLogger(__name__)


def calculate_file_hash(
    file_path: Path,
    algorithm: str = "sha256",
    chunk_size: int = 65536,
) -> Result[str]:
    """
    Calculate the hash of a file.
    
    Args:
        file_path: Path to the file.
        algorithm: Hash algorithm to use (sha256, md5, sha1).
        chunk_size: Size of chunks to read at a time.
    
    Returns:
        Result containing the hex digest of the hash.
    """
    try:
        file_path = Path(file_path).resolve()
        
        if not file_path.exists():
            return Failure(AppFileNotFoundError(
                message=f"File not found: {file_path}",
                path=file_path,
                operation="hash",
            ))
        
        hasher = hashlib.new(algorithm)
        
        with open(file_path, "rb") as file:
            for chunk in iter(lambda: file.read(chunk_size), b""):
                hasher.update(chunk)
        
        return Success(hasher.hexdigest())
        
    except PermissionError:
        return Failure(AppFilePermissionError(
            message=f"Permission denied: {file_path}",
            path=file_path,
            operation="hash",
        ))
    except Exception as exception:
        return Failure(FileSystemError(
            message=f"Failed to hash file: {str(exception)}",
            path=file_path,
            operation="hash",
        ))


def safe_file_copy(
    source_path: Path,
    destination_path: Path,
    overwrite: bool = False,
) -> Result[Path]:
    """
    Safely copy a file with error handling.
    
    Args:
        source_path: Source file path.
        destination_path: Destination file path.
        overwrite: Whether to overwrite existing destination.
    
    Returns:
        Result containing the destination path.
    """
    try:
        source_path = Path(source_path).resolve()
        destination_path = Path(destination_path).resolve()
        
        if not source_path.exists():
            return Failure(AppFileNotFoundError(
                message=f"Source file not found: {source_path}",
                path=source_path,
                operation="copy",
            ))
        
        if destination_path.exists() and not overwrite:
            return Failure(FileSystemError(
                message=f"Destination file already exists: {destination_path}",
                path=destination_path,
                operation="copy",
            ))
        
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        
        shutil.copy2(source_path, destination_path)
        
        logger.debug(f"Copied file: {source_path} -> {destination_path}")
        return Success(destination_path)
        
    except PermissionError:
        return Failure(AppFilePermissionError(
            message=f"Permission denied during copy",
            path=source_path,
            operation="copy",
        ))
    except Exception as exception:
        return Failure(FileSystemError(
            message=f"Failed to copy file: {str(exception)}",
            path=source_path,
            operation="copy",
        ))


def safe_file_move(
    source_path: Path,
    destination_path: Path,
    overwrite: bool = False,
) -> Result[Path]:
    """
    Safely move a file with error handling.
    
    Args:
        source_path: Source file path.
        destination_path: Destination file path.
        overwrite: Whether to overwrite existing destination.
    
    Returns:
        Result containing the destination path.
    """
    try:
        source_path = Path(source_path).resolve()
        destination_path = Path(destination_path).resolve()
        
        if not source_path.exists():
            return Failure(AppFileNotFoundError(
                message=f"Source file not found: {source_path}",
                path=source_path,
                operation="move",
            ))
        
        if destination_path.exists() and not overwrite:
            return Failure(FileSystemError(
                message=f"Destination file already exists: {destination_path}",
                path=destination_path,
                operation="move",
            ))
        
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        
        shutil.move(str(source_path), str(destination_path))
        
        logger.debug(f"Moved file: {source_path} -> {destination_path}")
        return Success(destination_path)
        
    except PermissionError:
        return Failure(AppFilePermissionError(
            message=f"Permission denied during move",
            path=source_path,
            operation="move",
        ))
    except Exception as exception:
        return Failure(FileSystemError(
            message=f"Failed to move file: {str(exception)}",
            path=source_path,
            operation="move",
        ))


def ensure_directory_exists(directory_path: Path) -> Result[Path]:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        directory_path: Path to the directory.
    
    Returns:
        Result containing the directory path.
    """
    try:
        directory_path = Path(directory_path).resolve()
        directory_path.mkdir(parents=True, exist_ok=True)
        return Success(directory_path)
    except PermissionError:
        return Failure(AppFilePermissionError(
            message=f"Permission denied creating directory: {directory_path}",
            path=directory_path,
            operation="mkdir",
        ))
    except Exception as exception:
        return Failure(FileSystemError(
            message=f"Failed to create directory: {str(exception)}",
            path=directory_path,
            operation="mkdir",
        ))


def get_unique_filename(
    directory: Path,
    base_name: str,
    extension: str,
) -> Path:
    """
    Generate a unique filename by appending a number if necessary.
    
    Args:
        directory: Directory where the file will be created.
        base_name: Base name for the file (without extension).
        extension: File extension (with or without leading dot).
    
    Returns:
        Path with unique filename.
    """
    if not extension.startswith("."):
        extension = f".{extension}"
    
    directory = Path(directory).resolve()
    
    candidate = directory / f"{base_name}{extension}"
    if not candidate.exists():
        return candidate
    
    counter = 1
    while True:
        candidate = directory / f"{base_name} ({counter}){extension}"
        if not candidate.exists():
            return candidate
        counter += 1
        
        if counter > 10000:
            raise RuntimeError("Could not generate unique filename")


def read_file_bytes(file_path: Path) -> Result[bytes]:
    """
    Read file contents as bytes.
    
    Args:
        file_path: Path to the file.
    
    Returns:
        Result containing the file bytes.
    """
    try:
        file_path = Path(file_path).resolve()
        
        if not file_path.exists():
            return Failure(AppFileNotFoundError(
                message=f"File not found: {file_path}",
                path=file_path,
                operation="read",
            ))
        
        with open(file_path, "rb") as file:
            return Success(file.read())
            
    except PermissionError:
        return Failure(AppFilePermissionError(
            message=f"Permission denied: {file_path}",
            path=file_path,
            operation="read",
        ))
    except Exception as exception:
        return Failure(FileSystemError(
            message=f"Failed to read file: {str(exception)}",
            path=file_path,
            operation="read",
        ))


def write_file_bytes(
    file_path: Path,
    data: bytes,
    overwrite: bool = True,
) -> Result[Path]:
    """
    Write bytes to a file.
    
    Args:
        file_path: Path to the file.
        data: Bytes to write.
        overwrite: Whether to overwrite existing file.
    
    Returns:
        Result containing the file path.
    """
    try:
        file_path = Path(file_path).resolve()
        
        if file_path.exists() and not overwrite:
            return Failure(FileSystemError(
                message=f"File already exists: {file_path}",
                path=file_path,
                operation="write",
            ))
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, "wb") as file:
            file.write(data)
        
        return Success(file_path)
        
    except PermissionError:
        return Failure(AppFilePermissionError(
            message=f"Permission denied: {file_path}",
            path=file_path,
            operation="write",
        ))
    except Exception as exception:
        return Failure(FileSystemError(
            message=f"Failed to write file: {str(exception)}",
            path=file_path,
            operation="write",
        ))


def read_file_text(
    file_path: Path,
    encoding: str = "utf-8",
) -> Result[str]:
    """
    Read file contents as text.
    
    Args:
        file_path: Path to the file.
        encoding: Text encoding.
    
    Returns:
        Result containing the file text.
    """
    try:
        file_path = Path(file_path).resolve()
        
        if not file_path.exists():
            return Failure(AppFileNotFoundError(
                message=f"File not found: {file_path}",
                path=file_path,
                operation="read",
            ))
        
        with open(file_path, "r", encoding=encoding) as file:
            return Success(file.read())
            
    except PermissionError:
        return Failure(AppFilePermissionError(
            message=f"Permission denied: {file_path}",
            path=file_path,
            operation="read",
        ))
    except UnicodeDecodeError:
        return Failure(FileSystemError(
            message=f"Failed to decode file with encoding {encoding}",
            path=file_path,
            operation="read",
        ))
    except Exception as exception:
        return Failure(FileSystemError(
            message=f"Failed to read file: {str(exception)}",
            path=file_path,
            operation="read",
        ))


def write_file_text(
    file_path: Path,
    text: str,
    encoding: str = "utf-8",
    overwrite: bool = True,
) -> Result[Path]:
    """
    Write text to a file.
    
    Args:
        file_path: Path to the file.
        text: Text to write.
        encoding: Text encoding.
        overwrite: Whether to overwrite existing file.
    
    Returns:
        Result containing the file path.
    """
    try:
        file_path = Path(file_path).resolve()
        
        if file_path.exists() and not overwrite:
            return Failure(FileSystemError(
                message=f"File already exists: {file_path}",
                path=file_path,
                operation="write",
            ))
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, "w", encoding=encoding) as file:
            file.write(text)
        
        return Success(file_path)
        
    except PermissionError:
        return Failure(AppFilePermissionError(
            message=f"Permission denied: {file_path}",
            path=file_path,
            operation="write",
        ))
    except Exception as exception:
        return Failure(FileSystemError(
            message=f"Failed to write file: {str(exception)}",
            path=file_path,
            operation="write",
        ))


def is_valid_pdf_file(file_path: Path) -> bool:
    """
    Check if a file is a valid PDF by examining its header.
    
    Args:
        file_path: Path to check.
    
    Returns:
        True if the file appears to be a valid PDF.
    """
    try:
        file_path = Path(file_path).resolve()
        
        if not file_path.exists():
            return False
        
        if file_path.suffix.lower() != ".pdf":
            return False
        
        with open(file_path, "rb") as file:
            header = file.read(8)
            return header.startswith(b"%PDF-")
            
    except Exception:
        return False


def get_file_size(file_path: Path) -> Result[int]:
    """
    Get the size of a file in bytes.
    
    Args:
        file_path: Path to the file.
    
    Returns:
        Result containing the file size.
    """
    try:
        file_path = Path(file_path).resolve()
        
        if not file_path.exists():
            return Failure(AppFileNotFoundError(
                message=f"File not found: {file_path}",
                path=file_path,
                operation="stat",
            ))
        
        return Success(file_path.stat().st_size)
        
    except PermissionError:
        return Failure(AppFilePermissionError(
            message=f"Permission denied: {file_path}",
            path=file_path,
            operation="stat",
        ))
    except Exception as exception:
        return Failure(FileSystemError(
            message=f"Failed to get file size: {str(exception)}",
            path=file_path,
            operation="stat",
        ))


def delete_file(file_path: Path) -> Result[bool]:
    """
    Delete a file.
    
    Args:
        file_path: Path to the file.
    
    Returns:
        Result containing True if deleted.
    """
    try:
        file_path = Path(file_path).resolve()
        
        if not file_path.exists():
            return Success(False)
        
        file_path.unlink()
        logger.debug(f"Deleted file: {file_path}")
        return Success(True)
        
    except PermissionError:
        return Failure(AppFilePermissionError(
            message=f"Permission denied: {file_path}",
            path=file_path,
            operation="delete",
        ))
    except Exception as exception:
        return Failure(FileSystemError(
            message=f"Failed to delete file: {str(exception)}",
            path=file_path,
            operation="delete",
        ))


def list_files_in_directory(
    directory_path: Path,
    pattern: str = "*",
    recursive: bool = False,
) -> Result[list[Path]]:
    """
    List files in a directory matching a pattern.
    
    Args:
        directory_path: Directory to list.
        pattern: Glob pattern to match.
        recursive: Whether to search recursively.
    
    Returns:
        Result containing list of file paths.
    """
    try:
        directory_path = Path(directory_path).resolve()
        
        if not directory_path.exists():
            return Failure(AppFileNotFoundError(
                message=f"Directory not found: {directory_path}",
                path=directory_path,
                operation="list",
            ))
        
        if not directory_path.is_dir():
            return Failure(FileSystemError(
                message=f"Path is not a directory: {directory_path}",
                path=directory_path,
                operation="list",
            ))
        
        if recursive:
            files = list(directory_path.rglob(pattern))
        else:
            files = list(directory_path.glob(pattern))
        
        return Success([f for f in files if f.is_file()])
        
    except PermissionError:
        return Failure(AppFilePermissionError(
            message=f"Permission denied: {directory_path}",
            path=directory_path,
            operation="list",
        ))
    except Exception as exception:
        return Failure(FileSystemError(
            message=f"Failed to list directory: {str(exception)}",
            path=directory_path,
            operation="list",
        ))
