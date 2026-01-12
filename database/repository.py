from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import TypeVar, Generic, Optional, List, Callable
from contextlib import contextmanager
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from database.schema import (
    DocumentRecord,
    AnnotationRecord,
    AnnotationVersionRecord,
    CollectionRecord,
    TagRecord,
    SearchIndexRecord,
    SettingsRecord,
    RecentFileRecord,
    create_session,
)
from core.error_types import (
    Result,
    Success,
    Failure,
    DatabaseError,
    DatabaseConnectionError,
    DatabaseQueryError,
)

T = TypeVar("T")
logger = logging.getLogger(__name__)


class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository implementing common CRUD operations.
    All methods return Result types for explicit error handling.
    """
    
    def __init__(self, session: Optional[Session] = None):
        self._session = session
        self._owns_session = session is None
    
    @property
    def session(self) -> Session:
        """Get or create a database session."""
        if self._session is None:
            self._session = create_session()
        return self._session
    
    @contextmanager
    def transaction(self):
        """Context manager for database transactions with automatic rollback on error."""
        try:
            yield self.session
            self.session.commit()
        except SQLAlchemyError as exception:
            self.session.rollback()
            raise exception
    
    def _execute_query(
        self,
        query_func: Callable[[Session], T],
        operation_name: str,
    ) -> Result[T]:
        """
        Execute a database query with error handling.
        
        Args:
            query_func: Function that takes a session and returns results.
            operation_name: Name of the operation for error reporting.
        
        Returns:
            Result containing query results or error.
        """
        try:
            result = query_func(self.session)
            return Success(result)
        except IntegrityError as exception:
            self.session.rollback()
            logger.error(f"Integrity error in {operation_name}: {exception}")
            return Failure(DatabaseQueryError(
                message=f"Data integrity violation in {operation_name}",
                operation=operation_name,
            ))
        except SQLAlchemyError as exception:
            self.session.rollback()
            logger.error(f"Database error in {operation_name}: {exception}")
            return Failure(DatabaseQueryError(
                message=f"Database error in {operation_name}: {str(exception)}",
                operation=operation_name,
            ))
    
    def _execute_mutation(
        self,
        mutation_func: Callable[[Session], T],
        operation_name: str,
    ) -> Result[T]:
        """
        Execute a database mutation with transaction handling.
        
        Args:
            mutation_func: Function that performs the mutation.
            operation_name: Name of the operation for error reporting.
        
        Returns:
            Result containing mutation result or error.
        """
        try:
            with self.transaction():
                result = mutation_func(self.session)
                return Success(result)
        except IntegrityError as exception:
            logger.error(f"Integrity error in {operation_name}: {exception}")
            return Failure(DatabaseQueryError(
                message=f"Data integrity violation in {operation_name}",
                operation=operation_name,
            ))
        except SQLAlchemyError as exception:
            logger.error(f"Database error in {operation_name}: {exception}")
            return Failure(DatabaseQueryError(
                message=f"Database error in {operation_name}: {str(exception)}",
                operation=operation_name,
            ))
    
    @abstractmethod
    def get_by_id(self, entity_id: int) -> Result[Optional[T]]:
        """Get an entity by its ID."""
        pass
    
    @abstractmethod
    def get_all(self, limit: Optional[int] = None, offset: int = 0) -> Result[List[T]]:
        """Get all entities with optional pagination."""
        pass
    
    @abstractmethod
    def create(self, entity: T) -> Result[T]:
        """Create a new entity."""
        pass
    
    @abstractmethod
    def update(self, entity: T) -> Result[T]:
        """Update an existing entity."""
        pass
    
    @abstractmethod
    def delete(self, entity_id: int) -> Result[bool]:
        """Delete an entity by ID."""
        pass


class DocumentRepository(BaseRepository[DocumentRecord]):
    """Repository for document CRUD operations."""
    
    def get_by_id(self, entity_id: int) -> Result[Optional[DocumentRecord]]:
        def query(session: Session) -> Optional[DocumentRecord]:
            return session.query(DocumentRecord).filter(
                DocumentRecord.id == entity_id
            ).first()
        return self._execute_query(query, "get_document_by_id")
    
    def get_by_file_path(self, file_path: Path) -> Result[Optional[DocumentRecord]]:
        def query(session: Session) -> Optional[DocumentRecord]:
            return session.query(DocumentRecord).filter(
                DocumentRecord.file_path == str(file_path)
            ).first()
        return self._execute_query(query, "get_document_by_file_path")
    
    def get_by_file_hash(self, file_hash: str) -> Result[Optional[DocumentRecord]]:
        def query(session: Session) -> Optional[DocumentRecord]:
            return session.query(DocumentRecord).filter(
                DocumentRecord.file_hash == file_hash
            ).first()
        return self._execute_query(query, "get_document_by_file_hash")
    
    def get_all(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> Result[List[DocumentRecord]]:
        def query(session: Session) -> List[DocumentRecord]:
            base_query = session.query(DocumentRecord).order_by(
                DocumentRecord.date_added.desc()
            ).offset(offset)
            if limit is not None:
                base_query = base_query.limit(limit)
            return base_query.all()
        return self._execute_query(query, "get_all_documents")
    
    def get_recent(self, limit: int = 10) -> Result[List[DocumentRecord]]:
        def query(session: Session) -> List[DocumentRecord]:
            return session.query(DocumentRecord).filter(
                DocumentRecord.date_last_opened.isnot(None)
            ).order_by(
                DocumentRecord.date_last_opened.desc()
            ).limit(limit).all()
        return self._execute_query(query, "get_recent_documents")
    
    def get_favorites(self) -> Result[List[DocumentRecord]]:
        def query(session: Session) -> List[DocumentRecord]:
            return session.query(DocumentRecord).filter(
                DocumentRecord.is_favorite == True
            ).order_by(DocumentRecord.file_name).all()
        return self._execute_query(query, "get_favorite_documents")
    
    def search_by_name(self, search_term: str) -> Result[List[DocumentRecord]]:
        def query(session: Session) -> List[DocumentRecord]:
            pattern = f"%{search_term}%"
            return session.query(DocumentRecord).filter(
                DocumentRecord.file_name.ilike(pattern)
            ).order_by(DocumentRecord.file_name).all()
        return self._execute_query(query, "search_documents_by_name")
    
    def create(self, entity: DocumentRecord) -> Result[DocumentRecord]:
        def mutation(session: Session) -> DocumentRecord:
            session.add(entity)
            session.flush()
            return entity
        return self._execute_mutation(mutation, "create_document")
    
    def update(self, entity: DocumentRecord) -> Result[DocumentRecord]:
        def mutation(session: Session) -> DocumentRecord:
            session.merge(entity)
            session.flush()
            return entity
        return self._execute_mutation(mutation, "update_document")
    
    def update_last_opened(self, document_id: int) -> Result[DocumentRecord]:
        def mutation(session: Session) -> DocumentRecord:
            document = session.query(DocumentRecord).filter(
                DocumentRecord.id == document_id
            ).first()
            if document is None:
                raise ValueError(f"Document with ID {document_id} not found")
            document.date_last_opened = datetime.now()
            document.open_count += 1
            session.flush()
            return document
        return self._execute_mutation(mutation, "update_document_last_opened")
    
    def update_view_state(
        self,
        document_id: int,
        page_number: int,
        zoom_level: float,
        scroll_x: float,
        scroll_y: float,
    ) -> Result[DocumentRecord]:
        def mutation(session: Session) -> DocumentRecord:
            document = session.query(DocumentRecord).filter(
                DocumentRecord.id == document_id
            ).first()
            if document is None:
                raise ValueError(f"Document with ID {document_id} not found")
            document.last_viewed_page = page_number
            document.last_zoom_level = zoom_level
            document.last_scroll_position_x = scroll_x
            document.last_scroll_position_y = scroll_y
            session.flush()
            return document
        return self._execute_mutation(mutation, "update_document_view_state")
    
    def toggle_favorite(self, document_id: int) -> Result[DocumentRecord]:
        def mutation(session: Session) -> DocumentRecord:
            document = session.query(DocumentRecord).filter(
                DocumentRecord.id == document_id
            ).first()
            if document is None:
                raise ValueError(f"Document with ID {document_id} not found")
            document.is_favorite = not document.is_favorite
            session.flush()
            return document
        return self._execute_mutation(mutation, "toggle_document_favorite")
    
    def delete(self, entity_id: int) -> Result[bool]:
        def mutation(session: Session) -> bool:
            document = session.query(DocumentRecord).filter(
                DocumentRecord.id == entity_id
            ).first()
            if document is None:
                return False
            session.delete(document)
            return True
        return self._execute_mutation(mutation, "delete_document")
    
    def count(self) -> Result[int]:
        def query(session: Session) -> int:
            return session.query(DocumentRecord).count()
        return self._execute_query(query, "count_documents")


class AnnotationRepository(BaseRepository[AnnotationRecord]):
    """Repository for annotation CRUD operations."""
    
    def get_by_id(self, entity_id: int) -> Result[Optional[AnnotationRecord]]:
        def query(session: Session) -> Optional[AnnotationRecord]:
            return session.query(AnnotationRecord).filter(
                AnnotationRecord.id == entity_id
            ).first()
        return self._execute_query(query, "get_annotation_by_id")
    
    def get_by_uuid(self, annotation_uuid: str) -> Result[Optional[AnnotationRecord]]:
        def query(session: Session) -> Optional[AnnotationRecord]:
            return session.query(AnnotationRecord).filter(
                AnnotationRecord.annotation_uuid == annotation_uuid
            ).first()
        return self._execute_query(query, "get_annotation_by_uuid")
    
    def get_all(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> Result[List[AnnotationRecord]]:
        def query(session: Session) -> List[AnnotationRecord]:
            base_query = session.query(AnnotationRecord).filter(
                AnnotationRecord.is_deleted == False
            ).offset(offset)
            if limit is not None:
                base_query = base_query.limit(limit)
            return base_query.all()
        return self._execute_query(query, "get_all_annotations")
    
    def get_for_document(
        self,
        document_id: int,
        version_branch: str = "main",
    ) -> Result[List[AnnotationRecord]]:
        def query(session: Session) -> List[AnnotationRecord]:
            return session.query(AnnotationRecord).filter(
                AnnotationRecord.document_id == document_id,
                AnnotationRecord.version_branch == version_branch,
                AnnotationRecord.is_deleted == False,
            ).order_by(
                AnnotationRecord.page_number,
                AnnotationRecord.z_index,
            ).all()
        return self._execute_query(query, "get_annotations_for_document")
    
    def get_for_page(
        self,
        document_id: int,
        page_number: int,
        version_branch: str = "main",
    ) -> Result[List[AnnotationRecord]]:
        def query(session: Session) -> List[AnnotationRecord]:
            return session.query(AnnotationRecord).filter(
                AnnotationRecord.document_id == document_id,
                AnnotationRecord.page_number == page_number,
                AnnotationRecord.version_branch == version_branch,
                AnnotationRecord.is_deleted == False,
            ).order_by(AnnotationRecord.z_index).all()
        return self._execute_query(query, "get_annotations_for_page")
    
    def get_by_type(
        self,
        document_id: int,
        annotation_type: str,
    ) -> Result[List[AnnotationRecord]]:
        def query(session: Session) -> List[AnnotationRecord]:
            return session.query(AnnotationRecord).filter(
                AnnotationRecord.document_id == document_id,
                AnnotationRecord.annotation_type == annotation_type,
                AnnotationRecord.is_deleted == False,
            ).all()
        return self._execute_query(query, "get_annotations_by_type")
    
    def get_version_branches(self, document_id: int) -> Result[List[str]]:
        def query(session: Session) -> List[str]:
            results = session.query(AnnotationRecord.version_branch).filter(
                AnnotationRecord.document_id == document_id
            ).distinct().all()
            return [row[0] for row in results]
        return self._execute_query(query, "get_annotation_version_branches")
    
    def create(self, entity: AnnotationRecord) -> Result[AnnotationRecord]:
        def mutation(session: Session) -> AnnotationRecord:
            session.add(entity)
            session.flush()
            return entity
        return self._execute_mutation(mutation, "create_annotation")
    
    def create_batch(
        self,
        entities: List[AnnotationRecord],
    ) -> Result[List[AnnotationRecord]]:
        def mutation(session: Session) -> List[AnnotationRecord]:
            session.add_all(entities)
            session.flush()
            return entities
        return self._execute_mutation(mutation, "create_annotations_batch")
    
    def update(self, entity: AnnotationRecord) -> Result[AnnotationRecord]:
        def mutation(session: Session) -> AnnotationRecord:
            entity.modified_at = datetime.now()
            session.merge(entity)
            session.flush()
            return entity
        return self._execute_mutation(mutation, "update_annotation")
    
    def soft_delete(self, entity_id: int) -> Result[bool]:
        def mutation(session: Session) -> bool:
            annotation = session.query(AnnotationRecord).filter(
                AnnotationRecord.id == entity_id
            ).first()
            if annotation is None:
                return False
            annotation.is_deleted = True
            annotation.modified_at = datetime.now()
            return True
        return self._execute_mutation(mutation, "soft_delete_annotation")
    
    def delete(self, entity_id: int) -> Result[bool]:
        def mutation(session: Session) -> bool:
            annotation = session.query(AnnotationRecord).filter(
                AnnotationRecord.id == entity_id
            ).first()
            if annotation is None:
                return False
            session.delete(annotation)
            return True
        return self._execute_mutation(mutation, "delete_annotation")
    
    def delete_for_document(self, document_id: int) -> Result[int]:
        def mutation(session: Session) -> int:
            count = session.query(AnnotationRecord).filter(
                AnnotationRecord.document_id == document_id
            ).delete()
            return count
        return self._execute_mutation(mutation, "delete_annotations_for_document")


class CollectionRepository(BaseRepository[CollectionRecord]):
    """Repository for collection CRUD operations."""
    
    def get_by_id(self, entity_id: int) -> Result[Optional[CollectionRecord]]:
        def query(session: Session) -> Optional[CollectionRecord]:
            return session.query(CollectionRecord).filter(
                CollectionRecord.id == entity_id
            ).first()
        return self._execute_query(query, "get_collection_by_id")
    
    def get_all(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> Result[List[CollectionRecord]]:
        def query(session: Session) -> List[CollectionRecord]:
            base_query = session.query(CollectionRecord).order_by(
                CollectionRecord.sort_order,
                CollectionRecord.name,
            ).offset(offset)
            if limit is not None:
                base_query = base_query.limit(limit)
            return base_query.all()
        return self._execute_query(query, "get_all_collections")
    
    def get_root_collections(self) -> Result[List[CollectionRecord]]:
        def query(session: Session) -> List[CollectionRecord]:
            return session.query(CollectionRecord).filter(
                CollectionRecord.parent_id.is_(None)
            ).order_by(
                CollectionRecord.sort_order,
                CollectionRecord.name,
            ).all()
        return self._execute_query(query, "get_root_collections")
    
    def get_children(self, parent_id: int) -> Result[List[CollectionRecord]]:
        def query(session: Session) -> List[CollectionRecord]:
            return session.query(CollectionRecord).filter(
                CollectionRecord.parent_id == parent_id
            ).order_by(
                CollectionRecord.sort_order,
                CollectionRecord.name,
            ).all()
        return self._execute_query(query, "get_collection_children")
    
    def create(self, entity: CollectionRecord) -> Result[CollectionRecord]:
        def mutation(session: Session) -> CollectionRecord:
            session.add(entity)
            session.flush()
            return entity
        return self._execute_mutation(mutation, "create_collection")
    
    def update(self, entity: CollectionRecord) -> Result[CollectionRecord]:
        def mutation(session: Session) -> CollectionRecord:
            entity.modified_at = datetime.now()
            session.merge(entity)
            session.flush()
            return entity
        return self._execute_mutation(mutation, "update_collection")
    
    def add_document(
        self,
        collection_id: int,
        document_id: int,
    ) -> Result[bool]:
        def mutation(session: Session) -> bool:
            collection = session.query(CollectionRecord).filter(
                CollectionRecord.id == collection_id
            ).first()
            document = session.query(DocumentRecord).filter(
                DocumentRecord.id == document_id
            ).first()
            if collection is None or document is None:
                return False
            if document not in collection.documents:
                collection.documents.append(document)
            return True
        return self._execute_mutation(mutation, "add_document_to_collection")
    
    def remove_document(
        self,
        collection_id: int,
        document_id: int,
    ) -> Result[bool]:
        def mutation(session: Session) -> bool:
            collection = session.query(CollectionRecord).filter(
                CollectionRecord.id == collection_id
            ).first()
            document = session.query(DocumentRecord).filter(
                DocumentRecord.id == document_id
            ).first()
            if collection is None or document is None:
                return False
            if document in collection.documents:
                collection.documents.remove(document)
            return True
        return self._execute_mutation(mutation, "remove_document_from_collection")
    
    def delete(self, entity_id: int) -> Result[bool]:
        def mutation(session: Session) -> bool:
            collection = session.query(CollectionRecord).filter(
                CollectionRecord.id == entity_id
            ).first()
            if collection is None:
                return False
            session.delete(collection)
            return True
        return self._execute_mutation(mutation, "delete_collection")


class TagRepository(BaseRepository[TagRecord]):
    """Repository for tag CRUD operations."""
    
    def get_by_id(self, entity_id: int) -> Result[Optional[TagRecord]]:
        def query(session: Session) -> Optional[TagRecord]:
            return session.query(TagRecord).filter(
                TagRecord.id == entity_id
            ).first()
        return self._execute_query(query, "get_tag_by_id")
    
    def get_by_name(self, name: str) -> Result[Optional[TagRecord]]:
        def query(session: Session) -> Optional[TagRecord]:
            return session.query(TagRecord).filter(
                TagRecord.name == name
            ).first()
        return self._execute_query(query, "get_tag_by_name")
    
    def get_all(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> Result[List[TagRecord]]:
        def query(session: Session) -> List[TagRecord]:
            base_query = session.query(TagRecord).order_by(
                TagRecord.name
            ).offset(offset)
            if limit is not None:
                base_query = base_query.limit(limit)
            return base_query.all()
        return self._execute_query(query, "get_all_tags")
    
    def get_or_create(self, name: str, color: Optional[str] = None) -> Result[TagRecord]:
        def mutation(session: Session) -> TagRecord:
            existing = session.query(TagRecord).filter(
                TagRecord.name == name
            ).first()
            if existing is not None:
                return existing
            new_tag = TagRecord(name=name, color=color)
            session.add(new_tag)
            session.flush()
            return new_tag
        return self._execute_mutation(mutation, "get_or_create_tag")
    
    def create(self, entity: TagRecord) -> Result[TagRecord]:
        def mutation(session: Session) -> TagRecord:
            session.add(entity)
            session.flush()
            return entity
        return self._execute_mutation(mutation, "create_tag")
    
    def update(self, entity: TagRecord) -> Result[TagRecord]:
        def mutation(session: Session) -> TagRecord:
            session.merge(entity)
            session.flush()
            return entity
        return self._execute_mutation(mutation, "update_tag")
    
    def add_to_document(
        self,
        tag_id: int,
        document_id: int,
    ) -> Result[bool]:
        def mutation(session: Session) -> bool:
            tag = session.query(TagRecord).filter(
                TagRecord.id == tag_id
            ).first()
            document = session.query(DocumentRecord).filter(
                DocumentRecord.id == document_id
            ).first()
            if tag is None or document is None:
                return False
            if tag not in document.tags:
                document.tags.append(tag)
            return True
        return self._execute_mutation(mutation, "add_tag_to_document")
    
    def remove_from_document(
        self,
        tag_id: int,
        document_id: int,
    ) -> Result[bool]:
        def mutation(session: Session) -> bool:
            tag = session.query(TagRecord).filter(
                TagRecord.id == tag_id
            ).first()
            document = session.query(DocumentRecord).filter(
                DocumentRecord.id == document_id
            ).first()
            if tag is None or document is None:
                return False
            if tag in document.tags:
                document.tags.remove(tag)
            return True
        return self._execute_mutation(mutation, "remove_tag_from_document")
    
    def delete(self, entity_id: int) -> Result[bool]:
        def mutation(session: Session) -> bool:
            tag = session.query(TagRecord).filter(
                TagRecord.id == entity_id
            ).first()
            if tag is None:
                return False
            session.delete(tag)
            return True
        return self._execute_mutation(mutation, "delete_tag")


class SearchRepository(BaseRepository[SearchIndexRecord]):
    """Repository for search index operations."""
    
    def get_by_id(self, entity_id: int) -> Result[Optional[SearchIndexRecord]]:
        def query(session: Session) -> Optional[SearchIndexRecord]:
            return session.query(SearchIndexRecord).filter(
                SearchIndexRecord.id == entity_id
            ).first()
        return self._execute_query(query, "get_search_entry_by_id")
    
    def get_all(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> Result[List[SearchIndexRecord]]:
        def query(session: Session) -> List[SearchIndexRecord]:
            base_query = session.query(SearchIndexRecord).offset(offset)
            if limit is not None:
                base_query = base_query.limit(limit)
            return base_query.all()
        return self._execute_query(query, "get_all_search_entries")
    
    def search_text(
        self,
        search_term: str,
        document_id: Optional[int] = None,
        limit: int = 100,
    ) -> Result[List[SearchIndexRecord]]:
        def query(session: Session) -> List[SearchIndexRecord]:
            pattern = f"%{search_term}%"
            base_query = session.query(SearchIndexRecord).filter(
                SearchIndexRecord.text_content.ilike(pattern)
            )
            if document_id is not None:
                base_query = base_query.filter(
                    SearchIndexRecord.document_id == document_id
                )
            return base_query.limit(limit).all()
        return self._execute_query(query, "search_text")
    
    def index_page(
        self,
        document_id: int,
        page_number: int,
        text_content: str,
    ) -> Result[SearchIndexRecord]:
        def mutation(session: Session) -> SearchIndexRecord:
            existing = session.query(SearchIndexRecord).filter(
                SearchIndexRecord.document_id == document_id,
                SearchIndexRecord.page_number == page_number,
            ).first()
            
            if existing is not None:
                existing.text_content = text_content
                existing.indexed_at = datetime.now()
                session.flush()
                return existing
            
            new_entry = SearchIndexRecord(
                document_id=document_id,
                page_number=page_number,
                text_content=text_content,
            )
            session.add(new_entry)
            session.flush()
            return new_entry
        return self._execute_mutation(mutation, "index_page")
    
    def index_document_batch(
        self,
        document_id: int,
        pages: List[tuple[int, str]],
    ) -> Result[int]:
        def mutation(session: Session) -> int:
            session.query(SearchIndexRecord).filter(
                SearchIndexRecord.document_id == document_id
            ).delete()
            
            entries = [
                SearchIndexRecord(
                    document_id=document_id,
                    page_number=page_number,
                    text_content=text_content,
                )
                for page_number, text_content in pages
            ]
            session.add_all(entries)
            session.flush()
            return len(entries)
        return self._execute_mutation(mutation, "index_document_batch")
    
    def create(self, entity: SearchIndexRecord) -> Result[SearchIndexRecord]:
        def mutation(session: Session) -> SearchIndexRecord:
            session.add(entity)
            session.flush()
            return entity
        return self._execute_mutation(mutation, "create_search_entry")
    
    def update(self, entity: SearchIndexRecord) -> Result[SearchIndexRecord]:
        def mutation(session: Session) -> SearchIndexRecord:
            session.merge(entity)
            session.flush()
            return entity
        return self._execute_mutation(mutation, "update_search_entry")
    
    def delete(self, entity_id: int) -> Result[bool]:
        def mutation(session: Session) -> bool:
            entry = session.query(SearchIndexRecord).filter(
                SearchIndexRecord.id == entity_id
            ).first()
            if entry is None:
                return False
            session.delete(entry)
            return True
        return self._execute_mutation(mutation, "delete_search_entry")
    
    def delete_for_document(self, document_id: int) -> Result[int]:
        def mutation(session: Session) -> int:
            count = session.query(SearchIndexRecord).filter(
                SearchIndexRecord.document_id == document_id
            ).delete()
            return count
        return self._execute_mutation(mutation, "delete_search_entries_for_document")
    
    def is_document_indexed(self, document_id: int) -> Result[bool]:
        def query(session: Session) -> bool:
            count = session.query(SearchIndexRecord).filter(
                SearchIndexRecord.document_id == document_id
            ).count()
            return count > 0
        return self._execute_query(query, "check_document_indexed")


class SettingsRepository(BaseRepository[SettingsRecord]):
    """Repository for application settings."""
    
    def get_by_id(self, entity_id: int) -> Result[Optional[SettingsRecord]]:
        def query(session: Session) -> Optional[SettingsRecord]:
            return session.query(SettingsRecord).filter(
                SettingsRecord.id == entity_id
            ).first()
        return self._execute_query(query, "get_setting_by_id")
    
    def get_by_key(self, key: str) -> Result[Optional[SettingsRecord]]:
        def query(session: Session) -> Optional[SettingsRecord]:
            return session.query(SettingsRecord).filter(
                SettingsRecord.key == key
            ).first()
        return self._execute_query(query, "get_setting_by_key")
    
    def get_all(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> Result[List[SettingsRecord]]:
        def query(session: Session) -> List[SettingsRecord]:
            base_query = session.query(SettingsRecord).offset(offset)
            if limit is not None:
                base_query = base_query.limit(limit)
            return base_query.all()
        return self._execute_query(query, "get_all_settings")
    
    def get_by_category(self, category: str) -> Result[List[SettingsRecord]]:
        def query(session: Session) -> List[SettingsRecord]:
            return session.query(SettingsRecord).filter(
                SettingsRecord.category == category
            ).all()
        return self._execute_query(query, "get_settings_by_category")
    
    def set_value(
        self,
        key: str,
        value: str,
        value_type: str = "string",
        category: Optional[str] = None,
    ) -> Result[SettingsRecord]:
        def mutation(session: Session) -> SettingsRecord:
            existing = session.query(SettingsRecord).filter(
                SettingsRecord.key == key
            ).first()
            
            if existing is not None:
                existing.value = value
                existing.value_type = value_type
                if category is not None:
                    existing.category = category
                session.flush()
                return existing
            
            new_setting = SettingsRecord(
                key=key,
                value=value,
                value_type=value_type,
                category=category,
            )
            session.add(new_setting)
            session.flush()
            return new_setting
        return self._execute_mutation(mutation, "set_setting_value")
    
    def create(self, entity: SettingsRecord) -> Result[SettingsRecord]:
        def mutation(session: Session) -> SettingsRecord:
            session.add(entity)
            session.flush()
            return entity
        return self._execute_mutation(mutation, "create_setting")
    
    def update(self, entity: SettingsRecord) -> Result[SettingsRecord]:
        def mutation(session: Session) -> SettingsRecord:
            session.merge(entity)
            session.flush()
            return entity
        return self._execute_mutation(mutation, "update_setting")
    
    def delete(self, entity_id: int) -> Result[bool]:
        def mutation(session: Session) -> bool:
            setting = session.query(SettingsRecord).filter(
                SettingsRecord.id == entity_id
            ).first()
            if setting is None:
                return False
            session.delete(setting)
            return True
        return self._execute_mutation(mutation, "delete_setting")
    
    def delete_by_key(self, key: str) -> Result[bool]:
        def mutation(session: Session) -> bool:
            setting = session.query(SettingsRecord).filter(
                SettingsRecord.key == key
            ).first()
            if setting is None:
                return False
            session.delete(setting)
            return True
        return self._execute_mutation(mutation, "delete_setting_by_key")
