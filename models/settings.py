from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional, Dict, Any, List
import json

from PyQt6.QtCore import QSettings


class Theme(Enum):
    """Application theme options."""
    SYSTEM = auto()
    LIGHT = auto()
    DARK = auto()


class DefaultViewMode(Enum):
    """Default PDF view mode."""
    SINGLE_PAGE = auto()
    CONTINUOUS = auto()
    FACING_PAGES = auto()
    BOOK_VIEW = auto()


class DefaultZoomMode(Enum):
    """Default zoom mode."""
    FIT_WIDTH = auto()
    FIT_PAGE = auto()
    ACTUAL_SIZE = auto()
    LAST_USED = auto()


@dataclass
class ViewerSettings:
    """Settings for the PDF viewer."""
    
    default_view_mode: DefaultViewMode = DefaultViewMode.CONTINUOUS
    default_zoom_mode: DefaultZoomMode = DefaultZoomMode.FIT_WIDTH
    default_zoom_level: float = 1.0
    
    smooth_scrolling: bool = True
    scroll_sensitivity: float = 1.0
    
    show_thumbnails: bool = True
    thumbnail_size: int = 150
    
    page_spacing: int = 10
    facing_page_gap: int = 20
    
    render_quality: str = "high"
    
    enable_page_preloading: bool = True
    preload_pages_count: int = 2
    
    invert_colors: bool = False
    sepia_mode: bool = False
    
    highlight_links: bool = True
    highlight_forms: bool = True
    
    remember_view_state: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary."""
        return {
            "default_view_mode": self.default_view_mode.name,
            "default_zoom_mode": self.default_zoom_mode.name,
            "default_zoom_level": self.default_zoom_level,
            "smooth_scrolling": self.smooth_scrolling,
            "scroll_sensitivity": self.scroll_sensitivity,
            "show_thumbnails": self.show_thumbnails,
            "thumbnail_size": self.thumbnail_size,
            "page_spacing": self.page_spacing,
            "facing_page_gap": self.facing_page_gap,
            "render_quality": self.render_quality,
            "enable_page_preloading": self.enable_page_preloading,
            "preload_pages_count": self.preload_pages_count,
            "invert_colors": self.invert_colors,
            "sepia_mode": self.sepia_mode,
            "highlight_links": self.highlight_links,
            "highlight_forms": self.highlight_forms,
            "remember_view_state": self.remember_view_state,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ViewerSettings:
        """Create settings from dictionary."""
        return cls(
            default_view_mode=DefaultViewMode[data.get("default_view_mode", "CONTINUOUS")],
            default_zoom_mode=DefaultZoomMode[data.get("default_zoom_mode", "FIT_WIDTH")],
            default_zoom_level=data.get("default_zoom_level", 1.0),
            smooth_scrolling=data.get("smooth_scrolling", True),
            scroll_sensitivity=data.get("scroll_sensitivity", 1.0),
            show_thumbnails=data.get("show_thumbnails", True),
            thumbnail_size=data.get("thumbnail_size", 150),
            page_spacing=data.get("page_spacing", 10),
            facing_page_gap=data.get("facing_page_gap", 20),
            render_quality=data.get("render_quality", "high"),
            enable_page_preloading=data.get("enable_page_preloading", True),
            preload_pages_count=data.get("preload_pages_count", 2),
            invert_colors=data.get("invert_colors", False),
            sepia_mode=data.get("sepia_mode", False),
            highlight_links=data.get("highlight_links", True),
            highlight_forms=data.get("highlight_forms", True),
            remember_view_state=data.get("remember_view_state", True),
        )


@dataclass
class AnnotationSettings:
    """Settings for annotation tools."""
    
    default_stroke_color: str = "#ff0000"
    default_stroke_width: float = 2.0
    
    default_fill_color: str = "#ffffff00"
    
    default_highlight_color: str = "#ffff0080"
    
    default_text_color: str = "#000000"
    default_font_family: str = "Arial"
    default_font_size: float = 12.0
    
    default_sticky_note_color: str = "#ffff00"
    
    enable_pressure_sensitivity: bool = True
    freehand_smoothing_level: int = 3
    
    snap_to_grid: bool = False
    grid_size: int = 10
    
    auto_save_annotations: bool = True
    auto_save_interval_seconds: int = 30
    
    show_annotation_tooltips: bool = True
    
    default_author_name: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary."""
        return {
            "default_stroke_color": self.default_stroke_color,
            "default_stroke_width": self.default_stroke_width,
            "default_fill_color": self.default_fill_color,
            "default_highlight_color": self.default_highlight_color,
            "default_text_color": self.default_text_color,
            "default_font_family": self.default_font_family,
            "default_font_size": self.default_font_size,
            "default_sticky_note_color": self.default_sticky_note_color,
            "enable_pressure_sensitivity": self.enable_pressure_sensitivity,
            "freehand_smoothing_level": self.freehand_smoothing_level,
            "snap_to_grid": self.snap_to_grid,
            "grid_size": self.grid_size,
            "auto_save_annotations": self.auto_save_annotations,
            "auto_save_interval_seconds": self.auto_save_interval_seconds,
            "show_annotation_tooltips": self.show_annotation_tooltips,
            "default_author_name": self.default_author_name,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AnnotationSettings:
        """Create settings from dictionary."""
        return cls(
            default_stroke_color=data.get("default_stroke_color", "#ff0000"),
            default_stroke_width=data.get("default_stroke_width", 2.0),
            default_fill_color=data.get("default_fill_color", "#ffffff00"),
            default_highlight_color=data.get("default_highlight_color", "#ffff0080"),
            default_text_color=data.get("default_text_color", "#000000"),
            default_font_family=data.get("default_font_family", "Arial"),
            default_font_size=data.get("default_font_size", 12.0),
            default_sticky_note_color=data.get("default_sticky_note_color", "#ffff00"),
            enable_pressure_sensitivity=data.get("enable_pressure_sensitivity", True),
            freehand_smoothing_level=data.get("freehand_smoothing_level", 3),
            snap_to_grid=data.get("snap_to_grid", False),
            grid_size=data.get("grid_size", 10),
            auto_save_annotations=data.get("auto_save_annotations", True),
            auto_save_interval_seconds=data.get("auto_save_interval_seconds", 30),
            show_annotation_tooltips=data.get("show_annotation_tooltips", True),
            default_author_name=data.get("default_author_name", ""),
        )


@dataclass
class ThemeSettings:
    """Settings for application appearance."""
    
    theme: Theme = Theme.SYSTEM
    
    accent_color: str = "#0078d4"
    
    custom_font_family: Optional[str] = None
    ui_font_size: int = 12
    
    toolbar_icon_size: int = 24
    show_toolbar_text: bool = True
    
    sidebar_width: int = 250
    
    window_opacity: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary."""
        return {
            "theme": self.theme.name,
            "accent_color": self.accent_color,
            "custom_font_family": self.custom_font_family,
            "ui_font_size": self.ui_font_size,
            "toolbar_icon_size": self.toolbar_icon_size,
            "show_toolbar_text": self.show_toolbar_text,
            "sidebar_width": self.sidebar_width,
            "window_opacity": self.window_opacity,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ThemeSettings:
        """Create settings from dictionary."""
        return cls(
            theme=Theme[data.get("theme", "SYSTEM")],
            accent_color=data.get("accent_color", "#0078d4"),
            custom_font_family=data.get("custom_font_family"),
            ui_font_size=data.get("ui_font_size", 12),
            toolbar_icon_size=data.get("toolbar_icon_size", 24),
            show_toolbar_text=data.get("show_toolbar_text", True),
            sidebar_width=data.get("sidebar_width", 250),
            window_opacity=data.get("window_opacity", 1.0),
        )


@dataclass
class PerformanceSettings:
    """Settings for performance tuning."""
    
    render_cache_size_mb: int = 200
    max_open_documents: int = 10
    
    background_thread_count: int = 4
    
    enable_hardware_acceleration: bool = True
    
    lazy_load_thumbnails: bool = True
    thumbnail_cache_size: int = 100
    
    search_result_limit: int = 1000
    
    database_connection_pool_size: int = 5
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary."""
        return {
            "render_cache_size_mb": self.render_cache_size_mb,
            "max_open_documents": self.max_open_documents,
            "background_thread_count": self.background_thread_count,
            "enable_hardware_acceleration": self.enable_hardware_acceleration,
            "lazy_load_thumbnails": self.lazy_load_thumbnails,
            "thumbnail_cache_size": self.thumbnail_cache_size,
            "search_result_limit": self.search_result_limit,
            "database_connection_pool_size": self.database_connection_pool_size,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PerformanceSettings:
        """Create settings from dictionary."""
        return cls(
            render_cache_size_mb=data.get("render_cache_size_mb", 200),
            max_open_documents=data.get("max_open_documents", 10),
            background_thread_count=data.get("background_thread_count", 4),
            enable_hardware_acceleration=data.get("enable_hardware_acceleration", True),
            lazy_load_thumbnails=data.get("lazy_load_thumbnails", True),
            thumbnail_cache_size=data.get("thumbnail_cache_size", 100),
            search_result_limit=data.get("search_result_limit", 1000),
            database_connection_pool_size=data.get("database_connection_pool_size", 5),
        )


@dataclass
class ShortcutSettings:
    """Keyboard shortcut configuration."""
    
    shortcuts: Dict[str, str] = field(default_factory=lambda: {
        "file_open": "Ctrl+O",
        "file_save": "Ctrl+S",
        "file_close": "Ctrl+W",
        "file_print": "Ctrl+P",
        "edit_undo": "Ctrl+Z",
        "edit_redo": "Ctrl+Y",
        "edit_copy": "Ctrl+C",
        "edit_paste": "Ctrl+V",
        "edit_select_all": "Ctrl+A",
        "view_zoom_in": "Ctrl++",
        "view_zoom_out": "Ctrl+-",
        "view_fit_width": "Ctrl+1",
        "view_fit_page": "Ctrl+2",
        "view_actual_size": "Ctrl+0",
        "navigate_next_page": "Right",
        "navigate_prev_page": "Left",
        "navigate_first_page": "Home",
        "navigate_last_page": "End",
        "navigate_go_to_page": "Ctrl+G",
        "search_find": "Ctrl+F",
        "search_find_next": "F3",
        "search_find_prev": "Shift+F3",
        "annotation_text": "T",
        "annotation_highlight": "H",
        "annotation_freehand": "D",
        "annotation_rectangle": "R",
        "annotation_sticky_note": "N",
        "fullscreen_toggle": "F11",
    })
    
    def get_shortcut(self, action: str) -> Optional[str]:
        """Get shortcut for an action."""
        return self.shortcuts.get(action)
    
    def set_shortcut(self, action: str, shortcut: str) -> None:
        """Set shortcut for an action."""
        self.shortcuts[action] = shortcut
    
    def reset_to_defaults(self) -> None:
        """Reset all shortcuts to defaults."""
        default = ShortcutSettings()
        self.shortcuts = default.shortcuts.copy()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary."""
        return {"shortcuts": self.shortcuts}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ShortcutSettings:
        """Create settings from dictionary."""
        default_shortcuts = ShortcutSettings().shortcuts
        loaded_shortcuts = data.get("shortcuts", {})
        merged = {**default_shortcuts, **loaded_shortcuts}
        return cls(shortcuts=merged)


class AppSettings:
    """
    Application settings manager with QSettings persistence.
    Singleton pattern for global access.
    """
    
    _instance: Optional[AppSettings] = None
    
    ORGANIZATION_NAME = "PDFViewer"
    APPLICATION_NAME = "PDFViewerPro"
    
    def __new__(cls) -> AppSettings:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._qsettings = QSettings(self.ORGANIZATION_NAME, self.APPLICATION_NAME)
        
        self.viewer = self._load_viewer_settings()
        self.annotation = self._load_annotation_settings()
        self.theme = self._load_theme_settings()
        self.performance = self._load_performance_settings()
        self.shortcuts = self._load_shortcut_settings()
        
        self.recent_files: List[str] = self._load_recent_files()
        self.recent_directories: List[str] = self._load_recent_directories()
        
        self.window_geometry: Optional[bytes] = self._qsettings.value("window/geometry")
        self.window_state: Optional[bytes] = self._qsettings.value("window/state")
        
        self._initialized = True
    
    def _load_viewer_settings(self) -> ViewerSettings:
        """Load viewer settings from QSettings."""
        data = self._qsettings.value("settings/viewer")
        if data:
            try:
                return ViewerSettings.from_dict(json.loads(data))
            except (json.JSONDecodeError, KeyError):
                pass
        return ViewerSettings()
    
    def _load_annotation_settings(self) -> AnnotationSettings:
        """Load annotation settings from QSettings."""
        data = self._qsettings.value("settings/annotation")
        if data:
            try:
                return AnnotationSettings.from_dict(json.loads(data))
            except (json.JSONDecodeError, KeyError):
                pass
        return AnnotationSettings()
    
    def _load_theme_settings(self) -> ThemeSettings:
        """Load theme settings from QSettings."""
        data = self._qsettings.value("settings/theme")
        if data:
            try:
                return ThemeSettings.from_dict(json.loads(data))
            except (json.JSONDecodeError, KeyError):
                pass
        return ThemeSettings()
    
    def _load_performance_settings(self) -> PerformanceSettings:
        """Load performance settings from QSettings."""
        data = self._qsettings.value("settings/performance")
        if data:
            try:
                return PerformanceSettings.from_dict(json.loads(data))
            except (json.JSONDecodeError, KeyError):
                pass
        return PerformanceSettings()
    
    def _load_shortcut_settings(self) -> ShortcutSettings:
        """Load shortcut settings from QSettings."""
        data = self._qsettings.value("settings/shortcuts")
        if data:
            try:
                return ShortcutSettings.from_dict(json.loads(data))
            except (json.JSONDecodeError, KeyError):
                pass
        return ShortcutSettings()
    
    def _load_recent_files(self) -> List[str]:
        """Load recent files list."""
        data = self._qsettings.value("recent/files", [])
        return data if isinstance(data, list) else []
    
    def _load_recent_directories(self) -> List[str]:
        """Load recent directories list."""
        data = self._qsettings.value("recent/directories", [])
        return data if isinstance(data, list) else []
    
    def save(self) -> None:
        """Save all settings to persistent storage."""
        self._qsettings.setValue("settings/viewer", json.dumps(self.viewer.to_dict()))
        self._qsettings.setValue("settings/annotation", json.dumps(self.annotation.to_dict()))
        self._qsettings.setValue("settings/theme", json.dumps(self.theme.to_dict()))
        self._qsettings.setValue("settings/performance", json.dumps(self.performance.to_dict()))
        self._qsettings.setValue("settings/shortcuts", json.dumps(self.shortcuts.to_dict()))
        
        self._qsettings.setValue("recent/files", self.recent_files)
        self._qsettings.setValue("recent/directories", self.recent_directories)
        
        if self.window_geometry:
            self._qsettings.setValue("window/geometry", self.window_geometry)
        if self.window_state:
            self._qsettings.setValue("window/state", self.window_state)
        
        self._qsettings.sync()
    
    def add_recent_file(self, file_path: str, max_recent: int = 20) -> None:
        """Add a file to the recent files list."""
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        self.recent_files.insert(0, file_path)
        self.recent_files = self.recent_files[:max_recent]
    
    def add_recent_directory(self, directory_path: str, max_recent: int = 10) -> None:
        """Add a directory to the recent directories list."""
        if directory_path in self.recent_directories:
            self.recent_directories.remove(directory_path)
        self.recent_directories.insert(0, directory_path)
        self.recent_directories = self.recent_directories[:max_recent]
    
    def clear_recent_files(self) -> None:
        """Clear the recent files list."""
        self.recent_files.clear()
    
    def reset_to_defaults(self) -> None:
        """Reset all settings to defaults."""
        self.viewer = ViewerSettings()
        self.annotation = AnnotationSettings()
        self.theme = ThemeSettings()
        self.performance = PerformanceSettings()
        self.shortcuts = ShortcutSettings()
    
    def save_window_state(self, geometry: bytes, state: bytes) -> None:
        """Save window geometry and state."""
        self.window_geometry = geometry
        self.window_state = state
    
    @property
    def data_directory(self) -> Path:
        """Get the application data directory."""
        return Path.home() / ".pdfviewer"
    
    @property
    def database_path(self) -> Path:
        """Get the database file path."""
        return self.data_directory / "library.db"
    
    @property
    def cache_directory(self) -> Path:
        """Get the cache directory path."""
        return self.data_directory / "cache"
    
    @property
    def thumbnails_directory(self) -> Path:
        """Get the thumbnails directory path."""
        return self.data_directory / "thumbnails"
