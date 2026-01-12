from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Optional
import json

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Table,
    JSON,
    LargeBinary,
    Index,
    UniqueConstraint,
    event,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    declarative_base,
    relationship,
    sessionmaker,
    Session,
)

Base = declarative_base()


DocumentTagAssociation = Table(
    "document_tag_association",
    Base.metadata,
    Column("document_id", Integer, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


DocumentCollectionAssociation = Table(
    "document_collection_association",
    Base.metadata,
    Column("document_id", Integer, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
    Column("collection_id", Integer, ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
)


class DocumentRecord(Base):
    """SQLAlchemy model for PDF documents in the library."""
    
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(String(1024), nullable=False, unique=True)
    file_name = Column(String(256), nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)
    file_size_bytes = Column(Integer, nullable=False)
    
    title = Column(String(512), nullable=True)
    author = Column(String(256), nullable=True)
    subject = Column(String(512), nullable=True)
    keywords = Column(Text, nullable=True)
    creator = Column(String(256), nullable=True)
    producer = Column(String(256), nullable=True)
    
    page_count = Column(Integer, nullable=False, default=0)
    creation_date = Column(DateTime, nullable=True)
    modification_date = Column(DateTime, nullable=True)
    
    thumbnail_data = Column(LargeBinary, nullable=True)
    
    date_added = Column(DateTime, nullable=False, default=datetime.now)
    date_last_opened = Column(DateTime, nullable=True)
    open_count = Column(Integer, nullable=False, default=0)
    
    last_viewed_page = Column(Integer, nullable=False, default=0)
    last_zoom_level = Column(Float, nullable=False, default=1.0)
    last_scroll_position_x = Column(Float, nullable=False, default=0.0)
    last_scroll_position_y = Column(Float, nullable=False, default=0.0)
    
    is_favorite = Column(Boolean, nullable=False, default=False)
    is_archived = Column(Boolean, nullable=False, default=False)
    
    custom_metadata = Column(JSON, nullable=True)
    
    annotations = relationship(
        "AnnotationRecord",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    
    tags = relationship(
        "TagRecord",
        secondary=DocumentTagAssociation,
        back_populates="documents",
        lazy="selectin",
    )
    
    collections = relationship(
        "CollectionRecord",
        secondary=DocumentCollectionAssociation,
        back_populates="documents",
        lazy="selectin",
    )
    
    search_entries = relationship(
        "SearchIndexRecord",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    
    __table_args__ = (
        Index("idx_documents_file_name", "file_name"),
        Index("idx_documents_date_added", "date_added"),
        Index("idx_documents_date_last_opened", "date_last_opened"),
    )


class AnnotationRecord(Base):
    """SQLAlchemy model for annotations on PDF documents."""
    
    __tablename__ = "annotations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    
    annotation_uuid = Column(String(36), nullable=False, unique=True, index=True)
    annotation_type = Column(String(50), nullable=False)
    
    page_number = Column(Integer, nullable=False)
    
    position_x = Column(Float, nullable=False)
    position_y = Column(Float, nullable=False)
    width = Column(Float, nullable=False, default=0.0)
    height = Column(Float, nullable=False, default=0.0)
    
    z_index = Column(Integer, nullable=False, default=0)
    
    content_data = Column(JSON, nullable=False)
    
    style_data = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    modified_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    created_by = Column(String(256), nullable=True)
    
    is_visible = Column(Boolean, nullable=False, default=True)
    is_locked = Column(Boolean, nullable=False, default=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    
    group_id = Column(String(36), nullable=True, index=True)
    
    version_branch = Column(String(64), nullable=False, default="main")
    
    document = relationship("DocumentRecord", back_populates="annotations")
    
    versions = relationship(
        "AnnotationVersionRecord",
        back_populates="annotation",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    
    __table_args__ = (
        Index("idx_annotations_document_page", "document_id", "page_number"),
        Index("idx_annotations_type", "annotation_type"),
        Index("idx_annotations_version_branch", "version_branch"),
    )


class AnnotationVersionRecord(Base):
    """SQLAlchemy model for annotation version history."""
    
    __tablename__ = "annotation_versions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    annotation_id = Column(Integer, ForeignKey("annotations.id", ondelete="CASCADE"), nullable=False)
    
    version_number = Column(Integer, nullable=False)
    
    delta_data = Column(JSON, nullable=False)
    
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    created_by = Column(String(256), nullable=True)
    
    annotation = relationship("AnnotationRecord", back_populates="versions")
    
    __table_args__ = (
        UniqueConstraint("annotation_id", "version_number", name="uq_annotation_version"),
    )


class CollectionRecord(Base):
    """SQLAlchemy model for virtual document collections."""
    
    __tablename__ = "collections"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    
    parent_id = Column(Integer, ForeignKey("collections.id", ondelete="CASCADE"), nullable=True)
    
    color = Column(String(7), nullable=True)
    icon = Column(String(64), nullable=True)
    
    sort_order = Column(Integer, nullable=False, default=0)
    
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    modified_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    
    is_smart_collection = Column(Boolean, nullable=False, default=False)
    smart_query = Column(JSON, nullable=True)
    
    documents = relationship(
        "DocumentRecord",
        secondary=DocumentCollectionAssociation,
        back_populates="collections",
        lazy="dynamic",
    )
    
    children = relationship(
        "CollectionRecord",
        backref="parent",
        remote_side=[id],
        lazy="selectin",
    )
    
    __table_args__ = (
        Index("idx_collections_parent", "parent_id"),
        Index("idx_collections_name", "name"),
    )


class TagRecord(Base):
    """SQLAlchemy model for document tags."""
    
    __tablename__ = "tags"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, unique=True)
    color = Column(String(7), nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    
    documents = relationship(
        "DocumentRecord",
        secondary=DocumentTagAssociation,
        back_populates="tags",
        lazy="dynamic",
    )
    
    __table_args__ = (
        Index("idx_tags_name", "name"),
    )


class SearchIndexRecord(Base):
    """SQLAlchemy model for full-text search index."""
    
    __tablename__ = "search_index"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_number = Column(Integer, nullable=False)
    
    text_content = Column(Text, nullable=False)
    
    indexed_at = Column(DateTime, nullable=False, default=datetime.now)
    
    document = relationship("DocumentRecord", back_populates="search_entries")
    
    __table_args__ = (
        Index("idx_search_document_page", "document_id", "page_number"),
        Index("idx_search_text_content", "text_content", mysql_length=255),
    )


class SettingsRecord(Base):
    """SQLAlchemy model for application settings persistence."""
    
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(256), nullable=False, unique=True)
    value = Column(JSON, nullable=False)
    value_type = Column(String(32), nullable=False, default="string")
    
    category = Column(String(64), nullable=True)
    
    modified_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    
    __table_args__ = (
        Index("idx_settings_category", "category"),
    )


class RecentFileRecord(Base):
    """SQLAlchemy model for tracking recently opened files."""
    
    __tablename__ = "recent_files"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(String(1024), nullable=False, unique=True)
    file_name = Column(String(256), nullable=False)
    
    opened_at = Column(DateTime, nullable=False, default=datetime.now)
    
    thumbnail_data = Column(LargeBinary, nullable=True)
    
    __table_args__ = (
        Index("idx_recent_files_opened_at", "opened_at"),
    )


_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable SQLite optimizations including foreign keys and WAL mode."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-64000")
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.close()


def get_engine(database_path: Optional[Path] = None) -> Engine:
    """
    Get or create the SQLAlchemy engine singleton.
    
    Args:
        database_path: Optional path to the database file. 
                      Defaults to 'library.db' in user data directory.
    
    Returns:
        The SQLAlchemy Engine instance.
    """
    global _engine
    
    if _engine is None:
        if database_path is None:
            database_path = Path.home() / ".pdfviewer" / "library.db"
        
        database_path.parent.mkdir(parents=True, exist_ok=True)
        
        connection_string = f"sqlite:///{database_path}"
        
        _engine = create_engine(
            connection_string,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            echo=False,
        )
    
    return _engine


def create_session(engine: Optional[Engine] = None) -> Session:
    """
    Create a new database session.
    
    Args:
        engine: Optional engine to use. Uses default if not provided.
    
    Returns:
        A new SQLAlchemy Session instance.
    """
    global _session_factory
    
    if engine is None:
        engine = get_engine()
    
    if _session_factory is None:
        _session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    
    return _session_factory()


def init_database(database_path: Optional[Path] = None) -> Engine:
    """
    Initialize the database, creating all tables if they don't exist.
    
    Args:
        database_path: Optional path to the database file.
    
    Returns:
        The initialized Engine instance.
    """
    engine = get_engine(database_path)
    Base.metadata.create_all(engine)
    return engine
