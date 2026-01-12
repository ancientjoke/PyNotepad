from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from enum import Enum, auto


@dataclass(frozen=True)
class DocumentMetadataModel:
    """Immutable PDF document metadata."""
    
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
    pdf_version: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "title": self.title,
            "author": self.author,
            "subject": self.subject,
            "keywords": self.keywords,
            "creator": self.creator,
            "producer": self.producer,
            "creation_date": self.creation_date.isoformat() if self.creation_date else None,
            "modification_date": self.modification_date.isoformat() if self.modification_date else None,
            "page_count": self.page_count,
            "file_size_bytes": self.file_size_bytes,
            "is_encrypted": self.is_encrypted,
            "pdf_version": self.pdf_version,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DocumentMetadataModel:
        """Create metadata from dictionary."""
        creation_date = None
        if data.get("creation_date"):
            creation_date = datetime.fromisoformat(data["creation_date"])
        
        modification_date = None
        if data.get("modification_date"):
            modification_date = datetime.fromisoformat(data["modification_date"])
        
        return cls(
            title=data.get("title"),
            author=data.get("author"),
            subject=data.get("subject"),
            keywords=data.get("keywords"),
            creator=data.get("creator"),
            producer=data.get("producer"),
            creation_date=creation_date,
            modification_date=modification_date,
            page_count=data.get("page_count", 0),
            file_size_bytes=data.get("file_size_bytes", 0),
            is_encrypted=data.get("is_encrypted", False),
            pdf_version=data.get("pdf_version"),
        )
    
    @property
    def display_title(self) -> str:
        """Get display title, falling back to empty string."""
        return self.title or ""
    
    @property
    def file_size_formatted(self) -> str:
        """Get human-readable file size."""
        size = self.file_size_bytes
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


@dataclass(frozen=True)
class ViewState:
    """Immutable document view state."""
    
    current_page: int = 0
    zoom_level: float = 1.0
    rotation: int = 0
    scroll_x: float = 0.0
    scroll_y: float = 0.0
    annotation_branch: str = "main"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert view state to dictionary."""
        return {
            "current_page": self.current_page,
            "zoom_level": self.zoom_level,
            "rotation": self.rotation,
            "scroll_x": self.scroll_x,
            "scroll_y": self.scroll_y,
            "annotation_branch": self.annotation_branch,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ViewState:
        """Create view state from dictionary."""
        return cls(
            current_page=data.get("current_page", 0),
            zoom_level=data.get("zoom_level", 1.0),
            rotation=data.get("rotation", 0),
            scroll_x=data.get("scroll_x", 0.0),
            scroll_y=data.get("scroll_y", 0.0),
            annotation_branch=data.get("annotation_branch", "main"),
        )
    
    def with_page(self, page: int) -> ViewState:
        """Create new ViewState with different page."""
        return ViewState(
            current_page=page,
            zoom_level=self.zoom_level,
            rotation=self.rotation,
            scroll_x=self.scroll_x,
            scroll_y=self.scroll_y,
            annotation_branch=self.annotation_branch,
        )
    
    def with_zoom(self, zoom: float) -> ViewState:
        """Create new ViewState with different zoom."""
        return ViewState(
            current_page=self.current_page,
            zoom_level=zoom,
            rotation=self.rotation,
            scroll_x=self.scroll_x,
            scroll_y=self.scroll_y,
            annotation_branch=self.annotation_branch,
        )
    
    def with_rotation(self, rotation: int) -> ViewState:
        """Create new ViewState with different rotation."""
        return ViewState(
            current_page=self.current_page,
            zoom_level=self.zoom_level,
            rotation=rotation % 360,
            scroll_x=self.scroll_x,
            scroll_y=self.scroll_y,
            annotation_branch=self.annotation_branch,
        )


@dataclass
class DocumentModel:
    """Domain model for PDF documents."""
    
    id: Optional[int]
    file_path: Path
    file_name: str
    file_hash: str
    metadata: DocumentMetadataModel
    
    date_added: datetime = field(default_factory=datetime.now)
    date_last_opened: Optional[datetime] = None
    open_count: int = 0
    
    thumbnail_data: Optional[bytes] = None
    
    view_state: ViewState = field(default_factory=ViewState)
    
    is_favorite: bool = False
    is_archived: bool = False
    
    tag_ids: List[int] = field(default_factory=list)
    collection_ids: List[int] = field(default_factory=list)
    
    custom_metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_record(cls, record) -> DocumentModel:
        """Create DocumentModel from database record."""
        metadata = DocumentMetadataModel(
            title=record.title,
            author=record.author,
            subject=record.subject,
            keywords=record.keywords,
            creator=record.creator,
            producer=record.producer,
            creation_date=record.creation_date,
            modification_date=record.modification_date,
            page_count=record.page_count,
            file_size_bytes=record.file_size_bytes,
        )
        
        view_state = ViewState(
            current_page=record.last_viewed_page,
            zoom_level=record.last_zoom_level,
            scroll_x=record.last_scroll_position_x,
            scroll_y=record.last_scroll_position_y,
        )
        
        return cls(
            id=record.id,
            file_path=Path(record.file_path),
            file_name=record.file_name,
            file_hash=record.file_hash,
            metadata=metadata,
            date_added=record.date_added,
            date_last_opened=record.date_last_opened,
            open_count=record.open_count,
            thumbnail_data=record.thumbnail_data,
            view_state=view_state,
            is_favorite=record.is_favorite,
            is_archived=record.is_archived,
            tag_ids=[tag.id for tag in record.tags],
            collection_ids=[col.id for col in record.collections],
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert document model to dictionary."""
        return {
            "id": self.id,
            "file_path": str(self.file_path),
            "file_name": self.file_name,
            "file_hash": self.file_hash,
            "metadata": self.metadata.to_dict(),
            "date_added": self.date_added.isoformat(),
            "date_last_opened": self.date_last_opened.isoformat() if self.date_last_opened else None,
            "open_count": self.open_count,
            "view_state": self.view_state.to_dict(),
            "is_favorite": self.is_favorite,
            "is_archived": self.is_archived,
            "tag_ids": self.tag_ids,
            "collection_ids": self.collection_ids,
            "custom_metadata": self.custom_metadata,
        }
    
    @property
    def display_name(self) -> str:
        """Get display name for the document."""
        if self.metadata.title:
            return self.metadata.title
        return self.file_name
    
    @property
    def exists(self) -> bool:
        """Check if the file still exists."""
        return self.file_path.exists()
    
    def mark_opened(self) -> None:
        """Mark document as opened (mutating)."""
        self.date_last_opened = datetime.now()
        self.open_count += 1
