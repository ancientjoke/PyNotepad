from __future__ import annotations
import sys
import os
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QDir
from PyQt6.QtGui import QIcon


def setup_environment() -> None:
    """Configure the application environment."""
    project_root = Path(__file__).parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    os.chdir(project_root)


def get_app_data_dir() -> Path:
    """Get the application data directory."""
    if sys.platform == "win32":
        app_data = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        app_data = Path.home() / "Library" / "Application Support"
    else:
        app_data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    
    data_dir = app_data / "NotepadPlusPlusPlus"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_cache_dir() -> Path:
    """Get the application cache directory."""
    if sys.platform == "win32":
        cache_base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        cache_base = Path.home() / "Library" / "Caches"
    else:
        cache_base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    
    cache_dir = cache_base / "NotepadPlusPlusPlus"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def initialize_database(data_dir: Path):
    """Initialize the application database."""
    from database.schema import init_database
    
    db_path = data_dir / "notepadplusplus.db"
    engine = init_database(db_path)
    
    return engine


def initialize_services(data_dir: Path, cache_dir: Path, engine):
    """Initialize application services."""
    from sqlalchemy.orm import sessionmaker
    from database.repository import (
        DocumentRepository,
        AnnotationRepository,
        CollectionRepository,
        TagRepository,
        SearchRepository,
        SettingsRepository,
    )
    from services.cache_service import CacheService
    from services.search_service import SearchService
    from services.import_service import ImportService
    from services.export_service import ExportService
    
    # Create session factory
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Initialize repositories
    repositories = {
        "document": DocumentRepository(session),
        "annotation": AnnotationRepository(session),
        "collection": CollectionRepository(session),
        "tag": TagRepository(session),
        "search": SearchRepository(session),
        "settings": SettingsRepository(session),
    }
    
    # Initialize cache service
    cache_service = CacheService()
    cache_service.initialize_disk_cache(cache_dir / "render_cache")
    
    # Initialize search service
    search_db_path = data_dir / "search_index.db"
    search_service = SearchService(search_db_path, repositories["document"])
    
    # Initialize import service
    library_path = data_dir / "library"
    library_path.mkdir(exist_ok=True)
    import_service = ImportService(repositories["document"], library_path)
    
    # Initialize export service
    export_service = ExportService()
    
    return {
        "repositories": repositories,
        "cache_service": cache_service,
        "search_service": search_service,
        "import_service": import_service,
        "export_service": export_service,
        "session": session,
    }


def create_main_window(services: dict):
    """Create and configure the main application window."""
    from ui.main_window import MainWindow
    
    window = MainWindow(services)
    window.setWindowTitle("Notepad+++ - PDF Viewer")
    window.resize(1400, 900)
    
    return window


def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler."""
    import traceback
    
    # Don't handle keyboard interrupt
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    # Log the error
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(f"Unhandled exception:\n{error_msg}", file=sys.stderr)
    
    # Show error dialog if QApplication exists
    app = QApplication.instance()
    if app:
        QMessageBox.critical(
            None,
            "Error",
            f"An unexpected error occurred:\n\n{exc_value}\n\nPlease check the logs for details.",
        )


def main():
    """Main application entry point."""
    # Setup environment
    setup_environment()
    
    # Install global exception handler
    sys.excepthook = handle_exception
    
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("Notepad+++")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Notepad+++")
    app.setOrganizationDomain("notepadplusplus.local")
    
    # Set application style
    app.setStyle("Fusion")
    
    # Get data directories
    data_dir = get_app_data_dir()
    cache_dir = get_cache_dir()
    
    try:
        # Initialize database
        engine = initialize_database(data_dir)
        
        # Initialize services
        services = initialize_services(data_dir, cache_dir, engine)
        
        # Create main window
        window = create_main_window(services)
        window.show()
        
        # Handle command line arguments
        if len(sys.argv) > 1:
            for arg in sys.argv[1:]:
                file_path = Path(arg)
                if file_path.exists() and file_path.suffix.lower() == ".pdf":
                    window.open_document(file_path)
        
        # Run application
        result = app.exec()
        
        # Cleanup
        services["session"].close()
        
        return result
        
    except Exception as e:
        QMessageBox.critical(
            None,
            "Startup Error",
            f"Failed to start application:\n\n{e}",
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())

