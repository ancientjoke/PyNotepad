"""Database package - Schema and repositories."""

__all__ = [
    "Base",
    "DocumentRecord",
    "AnnotationRecord",
    "CollectionRecord",
    "TagRecord",
    "DocumentTagAssociation",
    "DocumentCollectionAssociation",
    "AnnotationVersionRecord",
    "SearchIndexRecord",
    "SettingsRecord",
    "get_engine",
    "create_session",
    "init_database",
    "DocumentRepository",
    "AnnotationRepository",
    "CollectionRepository",
    "TagRepository",
    "SearchRepository",
    "SettingsRepository",
]

# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name in ("Base", "DocumentRecord", "AnnotationRecord", "CollectionRecord", "TagRecord",
                "DocumentTagAssociation", "DocumentCollectionAssociation", "AnnotationVersionRecord",
                "SearchIndexRecord", "SettingsRecord", "get_engine", "create_session", "init_database"):
        from database import schema
        return getattr(schema, name)
    elif name in ("DocumentRepository", "AnnotationRepository", "CollectionRepository",
                  "TagRepository", "SearchRepository", "SettingsRepository"):
        from database import repository
        return getattr(repository, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "Base",
    "DocumentRecord",
    "AnnotationRecord",
    "CollectionRecord",
    "TagRecord",
    "DocumentTagAssociation",
    "DocumentCollectionAssociation",
    "AnnotationVersionRecord",
    "SearchIndexRecord",
    "SettingsRecord",
    "get_engine",
    "create_session",
    "init_database",
    "DocumentRepository",
    "AnnotationRepository",
    "CollectionRepository",
    "TagRepository",
    "SearchRepository",
]
