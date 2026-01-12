from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional, List, Dict, Any


class SmartCollectionOperator(Enum):
    """Operators for smart collection queries."""
    EQUALS = auto()
    NOT_EQUALS = auto()
    CONTAINS = auto()
    NOT_CONTAINS = auto()
    STARTS_WITH = auto()
    ENDS_WITH = auto()
    GREATER_THAN = auto()
    LESS_THAN = auto()
    BETWEEN = auto()
    IS_EMPTY = auto()
    IS_NOT_EMPTY = auto()


class SmartCollectionField(Enum):
    """Fields available for smart collection queries."""
    FILE_NAME = auto()
    TITLE = auto()
    AUTHOR = auto()
    SUBJECT = auto()
    KEYWORDS = auto()
    PAGE_COUNT = auto()
    FILE_SIZE = auto()
    DATE_ADDED = auto()
    DATE_LAST_OPENED = auto()
    OPEN_COUNT = auto()
    IS_FAVORITE = auto()
    HAS_TAG = auto()


@dataclass
class SmartCollectionCondition:
    """Single condition in a smart collection query."""
    
    field: SmartCollectionField
    operator: SmartCollectionOperator
    value: Any
    value_secondary: Optional[Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert condition to dictionary."""
        return {
            "field": self.field.name,
            "operator": self.operator.name,
            "value": self.value,
            "value_secondary": self.value_secondary,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SmartCollectionCondition:
        """Create condition from dictionary."""
        return cls(
            field=SmartCollectionField[data["field"]],
            operator=SmartCollectionOperator[data["operator"]],
            value=data["value"],
            value_secondary=data.get("value_secondary"),
        )
    
    def evaluate(self, document) -> bool:
        """Evaluate this condition against a document."""
        field_value = self._get_field_value(document)
        
        if self.operator == SmartCollectionOperator.EQUALS:
            return field_value == self.value
        elif self.operator == SmartCollectionOperator.NOT_EQUALS:
            return field_value != self.value
        elif self.operator == SmartCollectionOperator.CONTAINS:
            return self.value.lower() in str(field_value).lower()
        elif self.operator == SmartCollectionOperator.NOT_CONTAINS:
            return self.value.lower() not in str(field_value).lower()
        elif self.operator == SmartCollectionOperator.STARTS_WITH:
            return str(field_value).lower().startswith(self.value.lower())
        elif self.operator == SmartCollectionOperator.ENDS_WITH:
            return str(field_value).lower().endswith(self.value.lower())
        elif self.operator == SmartCollectionOperator.GREATER_THAN:
            return field_value > self.value
        elif self.operator == SmartCollectionOperator.LESS_THAN:
            return field_value < self.value
        elif self.operator == SmartCollectionOperator.BETWEEN:
            return self.value <= field_value <= self.value_secondary
        elif self.operator == SmartCollectionOperator.IS_EMPTY:
            return not field_value
        elif self.operator == SmartCollectionOperator.IS_NOT_EMPTY:
            return bool(field_value)
        
        return False
    
    def _get_field_value(self, document) -> Any:
        """Extract the field value from a document."""
        field_map = {
            SmartCollectionField.FILE_NAME: lambda d: d.file_name,
            SmartCollectionField.TITLE: lambda d: d.metadata.title or "",
            SmartCollectionField.AUTHOR: lambda d: d.metadata.author or "",
            SmartCollectionField.SUBJECT: lambda d: d.metadata.subject or "",
            SmartCollectionField.KEYWORDS: lambda d: d.metadata.keywords or "",
            SmartCollectionField.PAGE_COUNT: lambda d: d.metadata.page_count,
            SmartCollectionField.FILE_SIZE: lambda d: d.metadata.file_size_bytes,
            SmartCollectionField.DATE_ADDED: lambda d: d.date_added,
            SmartCollectionField.DATE_LAST_OPENED: lambda d: d.date_last_opened,
            SmartCollectionField.OPEN_COUNT: lambda d: d.open_count,
            SmartCollectionField.IS_FAVORITE: lambda d: d.is_favorite,
            SmartCollectionField.HAS_TAG: lambda d: d.tag_ids,
        }
        
        getter = field_map.get(self.field, lambda d: None)
        return getter(document)


class SmartCollectionLogic(Enum):
    """Logical combination of conditions."""
    AND = auto()
    OR = auto()


@dataclass
class SmartCollectionQuery:
    """Query definition for smart collections."""
    
    conditions: List[SmartCollectionCondition] = field(default_factory=list)
    logic: SmartCollectionLogic = SmartCollectionLogic.AND
    
    def add_condition(self, condition: SmartCollectionCondition) -> None:
        """Add a condition to the query."""
        self.conditions.append(condition)
    
    def remove_condition(self, index: int) -> None:
        """Remove a condition by index."""
        if 0 <= index < len(self.conditions):
            self.conditions.pop(index)
    
    def evaluate(self, document) -> bool:
        """Evaluate the query against a document."""
        if not self.conditions:
            return True
        
        if self.logic == SmartCollectionLogic.AND:
            return all(condition.evaluate(document) for condition in self.conditions)
        else:
            return any(condition.evaluate(document) for condition in self.conditions)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert query to dictionary."""
        return {
            "conditions": [c.to_dict() for c in self.conditions],
            "logic": self.logic.name,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SmartCollectionQuery:
        """Create query from dictionary."""
        return cls(
            conditions=[
                SmartCollectionCondition.from_dict(c)
                for c in data.get("conditions", [])
            ],
            logic=SmartCollectionLogic[data.get("logic", "AND")],
        )


@dataclass
class CollectionModel:
    """Domain model for document collections."""
    
    id: Optional[int]
    name: str
    description: Optional[str] = None
    
    parent_id: Optional[int] = None
    
    color: Optional[str] = None
    icon: Optional[str] = None
    
    sort_order: int = 0
    
    is_smart_collection: bool = False
    smart_query: Optional[SmartCollectionQuery] = None
    
    document_ids: List[int] = field(default_factory=list)
    child_ids: List[int] = field(default_factory=list)
    
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    
    @classmethod
    def from_record(cls, record) -> CollectionModel:
        """Create CollectionModel from database record."""
        smart_query = None
        if record.is_smart_collection and record.smart_query:
            smart_query = SmartCollectionQuery.from_dict(record.smart_query)
        
        return cls(
            id=record.id,
            name=record.name,
            description=record.description,
            parent_id=record.parent_id,
            color=record.color,
            icon=record.icon,
            sort_order=record.sort_order,
            is_smart_collection=record.is_smart_collection,
            smart_query=smart_query,
            document_ids=[doc.id for doc in record.documents],
            child_ids=[child.id for child in record.children],
            created_at=record.created_at,
            modified_at=record.modified_at,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert collection to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "parent_id": self.parent_id,
            "color": self.color,
            "icon": self.icon,
            "sort_order": self.sort_order,
            "is_smart_collection": self.is_smart_collection,
            "smart_query": self.smart_query.to_dict() if self.smart_query else None,
            "document_ids": self.document_ids,
            "child_ids": self.child_ids,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
        }
    
    @property
    def document_count(self) -> int:
        """Get the number of documents in this collection."""
        return len(self.document_ids)
    
    @property
    def has_children(self) -> bool:
        """Check if this collection has child collections."""
        return len(self.child_ids) > 0
    
    @property
    def is_root(self) -> bool:
        """Check if this is a root-level collection."""
        return self.parent_id is None


@dataclass
class TagModel:
    """Domain model for document tags."""
    
    id: Optional[int]
    name: str
    color: Optional[str] = None
    
    document_ids: List[int] = field(default_factory=list)
    
    created_at: datetime = field(default_factory=datetime.now)
    
    @classmethod
    def from_record(cls, record) -> TagModel:
        """Create TagModel from database record."""
        return cls(
            id=record.id,
            name=record.name,
            color=record.color,
            document_ids=[doc.id for doc in record.documents],
            created_at=record.created_at,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tag to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "document_ids": self.document_ids,
            "created_at": self.created_at.isoformat(),
        }
    
    @property
    def document_count(self) -> int:
        """Get the number of documents with this tag."""
        return len(self.document_ids)
    
    @property
    def display_color(self) -> str:
        """Get display color, defaulting to gray if not set."""
        return self.color or "#808080"


class LibraryStatistics:
    """Statistics about the document library."""
    
    def __init__(
        self,
        total_documents: int = 0,
        total_pages: int = 0,
        total_size_bytes: int = 0,
        total_collections: int = 0,
        total_tags: int = 0,
        total_annotations: int = 0,
        favorite_count: int = 0,
        recently_opened_count: int = 0,
    ):
        self.total_documents = total_documents
        self.total_pages = total_pages
        self.total_size_bytes = total_size_bytes
        self.total_collections = total_collections
        self.total_tags = total_tags
        self.total_annotations = total_annotations
        self.favorite_count = favorite_count
        self.recently_opened_count = recently_opened_count
    
    @property
    def total_size_formatted(self) -> str:
        """Get formatted total size."""
        size = self.total_size_bytes
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert statistics to dictionary."""
        return {
            "total_documents": self.total_documents,
            "total_pages": self.total_pages,
            "total_size_bytes": self.total_size_bytes,
            "total_size_formatted": self.total_size_formatted,
            "total_collections": self.total_collections,
            "total_tags": self.total_tags,
            "total_annotations": self.total_annotations,
            "favorite_count": self.favorite_count,
            "recently_opened_count": self.recently_opened_count,
        }
