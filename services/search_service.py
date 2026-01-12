"""
Search Service

Provides full-text search capabilities for PDF content and metadata.
Features:
- Full-text indexing of PDF content
- Metadata search (title, author, tags)
- Search result ranking and highlighting
- Incremental index updates
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any
from enum import Enum, auto
import threading
import re
import sqlite3
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal

from core.error_types import (
    Result,
    Success,
    Failure,
    SearchError,
    DatabaseError,
)
from core.pdf_engine import PDFEngine
from database.repository import SearchRepository, DocumentRepository


class SearchScope(Enum):
    """Defines what to search."""
    ALL = auto()
    CONTENT = auto()
    METADATA = auto()
    ANNOTATIONS = auto()
    TITLE = auto()
    AUTHOR = auto()
    TAGS = auto()


class SearchOperator(Enum):
    """Boolean operators for search queries."""
    AND = auto()
    OR = auto()
    NOT = auto()
    PHRASE = auto()


@dataclass
class SearchQuery:
    """Represents a search query with options."""
    
    text: str
    scope: SearchScope = SearchScope.ALL
    case_sensitive: bool = False
    whole_word: bool = False
    use_regex: bool = False
    max_results: int = 100
    
    # Filters
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    collections: List[str] = field(default_factory=list)


@dataclass
class SearchMatch:
    """Represents a single match within a document."""
    
    page_number: int
    position: int  # Character position in the page text
    length: int  # Length of the match
    context: str  # Text snippet around the match
    relevance_score: float = 1.0


@dataclass
class SearchResult:
    """Represents a document that matches a search query."""
    
    document_id: str
    document_title: str
    file_path: str
    matches: List[SearchMatch] = field(default_factory=list)
    total_matches: int = 0
    relevance_score: float = 0.0
    matched_in: List[str] = field(default_factory=list)  # e.g., ["content", "title", "tags"]


@dataclass
class SearchResults:
    """Container for search results."""
    
    query: SearchQuery
    results: List[SearchResult] = field(default_factory=list)
    total_results: int = 0
    search_time_ms: float = 0.0
    is_truncated: bool = False


class SearchIndexer:
    """
    Handles indexing of PDF content for search.
    
    Uses SQLite FTS5 for full-text search capabilities.
    """
    
    def __init__(self, database_path: Path):
        self._database_path = database_path
        self._pdf_engine = PDFEngine()
        self._lock = threading.Lock()
        
        self._initialize_fts()
    
    def _initialize_fts(self) -> None:
        """Initialize FTS5 virtual table."""
        with sqlite3.connect(self._database_path) as conn:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
                    document_id,
                    page_number,
                    content,
                    tokenize='porter unicode61'
                )
            """)
            
            # Create metadata FTS table
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS metadata_fts USING fts5(
                    document_id,
                    title,
                    author,
                    tags,
                    tokenize='porter unicode61'
                )
            """)
            
            conn.commit()
    
    def index_document(
        self,
        document_id: str,
        file_path: Path,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Result[int]:
        """
        Index a document's content and metadata.
        
        Args:
            document_id: Unique document identifier.
            file_path: Path to the PDF file.
            metadata: Optional metadata dictionary.
        
        Returns:
            Result containing the number of pages indexed.
        """
        # Open document
        doc_result = self._pdf_engine.load_document(file_path)
        if doc_result.is_failure():
            return Failure(SearchError(
                message=f"Failed to open document: {doc_result.get_error()}",
            ))
        
        pdf_doc = doc_result.unwrap()
        pages_indexed = 0
        
        try:
            with self._lock:
                with sqlite3.connect(self._database_path) as conn:
                    # Remove existing index entries for this document
                    conn.execute(
                        "DELETE FROM search_fts WHERE document_id = ?",
                        (document_id,)
                    )
                    conn.execute(
                        "DELETE FROM metadata_fts WHERE document_id = ?",
                        (document_id,)
                    )
                    
                    # Index content page by page
                    page_count = pdf_doc.page_count
                    
                    for page_num in range(page_count):
                        text_result = pdf_doc.get_page_text(page_num)
                        if text_result.is_success():
                            text = text_result.unwrap()
                            if text:
                                conn.execute(
                                    "INSERT INTO search_fts (document_id, page_number, content) VALUES (?, ?, ?)",
                                    (document_id, page_num, text)
                                )
                                pages_indexed += 1
                    
                    # Index metadata
                    if metadata:
                        conn.execute(
                            "INSERT INTO metadata_fts (document_id, title, author, tags) VALUES (?, ?, ?, ?)",
                            (
                                document_id,
                                metadata.get("title", ""),
                                metadata.get("author", ""),
                                " ".join(metadata.get("tags", [])),
                            )
                        )
                    
                    conn.commit()
            
            return Success(pages_indexed)
        
        finally:
            pdf_doc.close()
    
    def remove_document(self, document_id: str) -> Result[None]:
        """Remove a document from the search index."""
        with self._lock:
            try:
                with sqlite3.connect(self._database_path) as conn:
                    conn.execute(
                        "DELETE FROM search_fts WHERE document_id = ?",
                        (document_id,)
                    )
                    conn.execute(
                        "DELETE FROM metadata_fts WHERE document_id = ?",
                        (document_id,)
                    )
                    conn.commit()
                return Success(None)
            except Exception as e:
                return Failure(DatabaseError(
                    message=f"Failed to remove from index: {e}",
                    operation="delete",
                ))
    
    def search_content(
        self,
        query: str,
        max_results: int = 100,
    ) -> Result[List[tuple[str, int, str]]]:
        """
        Search document content.
        
        Returns:
            List of (document_id, page_number, snippet) tuples.
        """
        with self._lock:
            try:
                with sqlite3.connect(self._database_path) as conn:
                    cursor = conn.execute(
                        """
                        SELECT document_id, page_number, snippet(search_fts, 2, '<mark>', '</mark>', '...', 50)
                        FROM search_fts
                        WHERE search_fts MATCH ?
                        ORDER BY rank
                        LIMIT ?
                        """,
                        (query, max_results)
                    )
                    results = cursor.fetchall()
                return Success(results)
            except Exception as e:
                return Failure(SearchError(
                    message=f"Search failed: {e}",
                    query=query,
                ))
    
    def search_metadata(
        self,
        query: str,
        max_results: int = 100,
    ) -> Result[List[tuple[str, str, str]]]:
        """
        Search document metadata.
        
        Returns:
            List of (document_id, field, snippet) tuples.
        """
        with self._lock:
            try:
                with sqlite3.connect(self._database_path) as conn:
                    cursor = conn.execute(
                        """
                        SELECT document_id, 
                               snippet(metadata_fts, 1, '<mark>', '</mark>', '...', 20),
                               snippet(metadata_fts, 2, '<mark>', '</mark>', '...', 20)
                        FROM metadata_fts
                        WHERE metadata_fts MATCH ?
                        ORDER BY rank
                        LIMIT ?
                        """,
                        (query, max_results)
                    )
                    results = cursor.fetchall()
                return Success(results)
            except Exception as e:
                return Failure(SearchError(
                    message=f"Search failed: {e}",
                    query=query,
                ))
    
    def get_index_stats(self) -> Dict[str, int]:
        """Get statistics about the search index."""
        with self._lock:
            with sqlite3.connect(self._database_path) as conn:
                content_count = conn.execute(
                    "SELECT COUNT(DISTINCT document_id) FROM search_fts"
                ).fetchone()[0]
                
                page_count = conn.execute(
                    "SELECT COUNT(*) FROM search_fts"
                ).fetchone()[0]
                
                metadata_count = conn.execute(
                    "SELECT COUNT(*) FROM metadata_fts"
                ).fetchone()[0]
                
                return {
                    "indexed_documents": content_count,
                    "indexed_pages": page_count,
                    "metadata_entries": metadata_count,
                }


class SearchService(QObject):
    """
    Service for searching across the document library.
    
    Signals:
        search_started: Emitted when search begins
        search_completed: Emitted with results (SearchResults)
        indexing_progress: Emitted during indexing (current, total)
    """
    
    search_started = pyqtSignal()
    search_completed = pyqtSignal(object)  # SearchResults
    indexing_progress = pyqtSignal(int, int)
    
    def __init__(
        self,
        database_path: Path,
        document_repository: DocumentRepository,
    ):
        super().__init__()
        
        self._indexer = SearchIndexer(database_path)
        self._document_repo = document_repository
        self._lock = threading.Lock()
    
    def search(self, query: SearchQuery) -> Result[SearchResults]:
        """
        Execute a search query.
        
        Args:
            query: The search query with options.
        
        Returns:
            Result containing SearchResults.
        """
        import time
        start_time = time.time()
        
        self.search_started.emit()
        
        results = SearchResults(query=query)
        
        # Escape special characters if not using regex
        search_text = query.text
        if not query.use_regex:
            # Convert to FTS5 query format
            search_text = self._prepare_fts_query(search_text)
        
        if not search_text:
            return Success(results)
        
        # Search based on scope
        document_matches: Dict[str, SearchResult] = {}
        
        if query.scope in (SearchScope.ALL, SearchScope.CONTENT):
            content_results = self._indexer.search_content(
                search_text,
                query.max_results,
            )
            if content_results.is_success():
                for doc_id, page_num, snippet in content_results.unwrap():
                    if doc_id not in document_matches:
                        doc_info = self._get_document_info(doc_id)
                        document_matches[doc_id] = SearchResult(
                            document_id=doc_id,
                            document_title=doc_info.get("title", "Unknown"),
                            file_path=doc_info.get("file_path", ""),
                        )
                    
                    document_matches[doc_id].matches.append(SearchMatch(
                        page_number=page_num,
                        position=0,
                        length=len(query.text),
                        context=snippet,
                    ))
                    document_matches[doc_id].total_matches += 1
                    if "content" not in document_matches[doc_id].matched_in:
                        document_matches[doc_id].matched_in.append("content")
        
        if query.scope in (SearchScope.ALL, SearchScope.METADATA, SearchScope.TITLE, SearchScope.AUTHOR):
            metadata_results = self._indexer.search_metadata(
                search_text,
                query.max_results,
            )
            if metadata_results.is_success():
                for doc_id, title_snippet, author_snippet in metadata_results.unwrap():
                    if doc_id not in document_matches:
                        doc_info = self._get_document_info(doc_id)
                        document_matches[doc_id] = SearchResult(
                            document_id=doc_id,
                            document_title=doc_info.get("title", "Unknown"),
                            file_path=doc_info.get("file_path", ""),
                        )
                    
                    if title_snippet and "<mark>" in title_snippet:
                        document_matches[doc_id].matched_in.append("title")
                    if author_snippet and "<mark>" in author_snippet:
                        document_matches[doc_id].matched_in.append("author")
        
        # Apply filters
        filtered_results = list(document_matches.values())
        
        if query.tags:
            filtered_results = [
                r for r in filtered_results
                if self._document_has_tags(r.document_id, query.tags)
            ]
        
        if query.collections:
            filtered_results = [
                r for r in filtered_results
                if self._document_in_collections(r.document_id, query.collections)
            ]
        
        # Calculate relevance scores
        for result in filtered_results:
            result.relevance_score = self._calculate_relevance(result, query)
        
        # Sort by relevance
        filtered_results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        # Limit results
        if len(filtered_results) > query.max_results:
            filtered_results = filtered_results[:query.max_results]
            results.is_truncated = True
        
        results.results = filtered_results
        results.total_results = len(filtered_results)
        results.search_time_ms = (time.time() - start_time) * 1000
        
        self.search_completed.emit(results)
        
        return Success(results)
    
    def search_in_document(
        self,
        document_id: str,
        query: str,
        case_sensitive: bool = False,
    ) -> Result[List[SearchMatch]]:
        """
        Search within a specific document.
        
        Args:
            document_id: Document to search in.
            query: Search text.
            case_sensitive: Whether search is case-sensitive.
        
        Returns:
            List of matches within the document.
        """
        fts_query = f'document_id:"{document_id}" AND ({self._prepare_fts_query(query)})'
        
        content_results = self._indexer.search_content(fts_query, 1000)
        if content_results.is_failure():
            return Failure(content_results.get_error())
        
        matches = []
        for doc_id, page_num, snippet in content_results.unwrap():
            if doc_id == document_id:
                matches.append(SearchMatch(
                    page_number=page_num,
                    position=0,
                    length=len(query),
                    context=snippet,
                ))
        
        return Success(matches)
    
    def index_document(
        self,
        document_id: str,
        file_path: Path,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Result[int]:
        """Index a document for searching."""
        return self._indexer.index_document(document_id, file_path, metadata)
    
    def remove_from_index(self, document_id: str) -> Result[None]:
        """Remove a document from the search index."""
        return self._indexer.remove_document(document_id)
    
    def reindex_all(
        self,
        progress_callback: Optional[callable] = None,
    ) -> Result[int]:
        """
        Reindex all documents in the library.
        
        Returns:
            Total number of pages indexed.
        """
        all_docs = self._document_repo.get_all()
        if all_docs.is_failure():
            return Failure(all_docs.get_error())
        
        documents = all_docs.unwrap()
        total_pages = 0
        
        for i, doc in enumerate(documents):
            if progress_callback:
                progress_callback(i + 1, len(documents))
            self.indexing_progress.emit(i + 1, len(documents))
            
            result = self._indexer.index_document(
                doc.id,
                Path(doc.file_path),
                {"title": doc.title, "author": doc.author},
            )
            if result.is_success():
                total_pages += result.unwrap()
        
        return Success(total_pages)
    
    def get_suggestions(
        self,
        partial_query: str,
        max_suggestions: int = 10,
    ) -> List[str]:
        """
        Get search suggestions based on partial input.
        
        Args:
            partial_query: Partial search text.
            max_suggestions: Maximum number of suggestions.
        
        Returns:
            List of suggested search terms.
        """
        # Simple implementation - could be enhanced with more sophisticated completion
        suggestions = set()
        
        # Search for documents with titles matching the partial query
        all_docs = self._document_repo.get_all()
        if all_docs.is_success():
            query_lower = partial_query.lower()
            for doc in all_docs.unwrap():
                if doc.title and query_lower in doc.title.lower():
                    suggestions.add(doc.title)
                if doc.author and query_lower in doc.author.lower():
                    suggestions.add(doc.author)
                
                if len(suggestions) >= max_suggestions:
                    break
        
        return list(suggestions)[:max_suggestions]
    
    def get_index_stats(self) -> Dict[str, int]:
        """Get search index statistics."""
        return self._indexer.get_index_stats()
    
    def _prepare_fts_query(self, text: str) -> str:
        """Prepare text for FTS5 query."""
        # Escape special FTS5 characters
        special_chars = ['*', '"', '(', ')', '-', '+', ':']
        result = text
        for char in special_chars:
            result = result.replace(char, f' ')
        
        # Split into words and join with OR for better matching
        words = result.split()
        if not words:
            return ""
        
        if len(words) == 1:
            return f'"{words[0]}"*'
        
        return ' OR '.join(f'"{word}"*' for word in words)
    
    def _get_document_info(self, document_id: str) -> Dict[str, Any]:
        """Get basic document information."""
        doc_result = self._document_repo.get_by_id(int(document_id) if document_id.isdigit() else 0)
        if doc_result.is_success():
            doc = doc_result.unwrap()
            if doc:
                return {
                    "title": doc.title,
                    "file_path": doc.file_path,
                    "author": doc.author,
                }
        return {}
    
    def _document_has_tags(self, document_id: str, tags: List[str]) -> bool:
        """Check if document has any of the specified tags."""
        # This would need to query the tag associations
        # Simplified implementation
        return True
    
    def _document_in_collections(self, document_id: str, collections: List[str]) -> bool:
        """Check if document is in any of the specified collections."""
        # This would need to query the collection associations
        # Simplified implementation
        return True
    
    def _calculate_relevance(self, result: SearchResult, query: SearchQuery) -> float:
        """Calculate relevance score for a search result."""
        score = 0.0
        
        # Base score from match count
        score += min(result.total_matches * 0.1, 5.0)
        
        # Boost for title matches
        if "title" in result.matched_in:
            score += 3.0
        
        # Boost for author matches
        if "author" in result.matched_in:
            score += 2.0
        
        # Boost for content matches
        if "content" in result.matched_in:
            score += 1.0
        
        return score
