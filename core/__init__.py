"""Core package - PDF engine, rendering, and document management."""

__all__ = [
    "Result",
    "Success", 
    "Failure",
    "PDFError",
    "RenderError",
    "DatabaseError",
    "ValidationError",
    "PDFEngine",
    "RenderEngine",
    "DocumentManager",
]

# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name in ("Result", "Success", "Failure", "PDFError", "RenderError", "DatabaseError", "ValidationError"):
        from core.error_types import Result, Success, Failure, PDFError, RenderError, DatabaseError, ValidationError
        return locals()[name]
    elif name == "PDFEngine":
        from core.pdf_engine import PDFEngine
        return PDFEngine
    elif name == "RenderEngine":
        from core.render_engine import RenderEngine
        return RenderEngine
    elif name == "DocumentManager":
        from core.document_manager import DocumentManager
        return DocumentManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
