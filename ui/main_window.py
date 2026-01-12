"""
Main Window

The primary application window containing all major UI components.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTabWidget,
    QMenuBar,
    QMenu,
    QToolBar,
    QStatusBar,
    QFileDialog,
    QMessageBox,
    QLabel,
    QDockWidget,
    QApplication,
    QInputDialog,
)
from PyQt6.QtCore import Qt, QSettings, QSize, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence, QIcon, QColor

from ui.viewer_widget import ViewerWidget
from ui.writer_widget import WriterWidget
from ui.library_panel import LibraryPanel
from ui.toolbar import MainToolBar
from ui.annotation_toolbar import AnnotationToolBar
from ui.writer_toolbar import WriterToolBar
from ui.dialogs.equation_dialog import EquationDialog


class MainWindow(QMainWindow):
    """
    Main application window.
    
    Contains the PDF viewer, document writer, library panel, annotation tools, and menu bar.
    
    Signals:
        document_opened: Emitted when a document is opened (path)
        document_closed: Emitted when a document is closed (path)
    """
    
    document_opened = pyqtSignal(str)
    document_closed = pyqtSignal(str)
    
    def __init__(self, services: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self._services = services
        self._settings = QSettings()
        self._current_document: Optional[Path] = None
        
        self._setup_ui()
        self._create_menus()
        self._create_toolbars()
        self._create_statusbar()
        self._connect_signals()
        self._restore_state()
    
    def _setup_ui(self) -> None:
        """Set up the main UI layout."""
        # Central widget with splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Main splitter for library panel and viewer
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self._main_splitter)
        
        # Library panel (left side)
        self._library_panel = LibraryPanel(self._services)
        self._main_splitter.addWidget(self._library_panel)
        
        # Tab widget for multiple documents (center)
        self._tab_widget = QTabWidget()
        self._tab_widget.setTabsClosable(True)
        self._tab_widget.setMovable(True)
        self._tab_widget.setDocumentMode(True)
        self._main_splitter.addWidget(self._tab_widget)
        
        # Set splitter sizes
        self._main_splitter.setSizes([250, 1150])
        
        # Minimum sizes
        self._library_panel.setMinimumWidth(200)
        self._tab_widget.setMinimumWidth(400)
    
    def _create_menus(self) -> None:
        """Create the menu bar and menus."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        # New submenu
        new_menu = QMenu("&New", self)
        file_menu.addMenu(new_menu)
        
        self._action_new_document = QAction("&Document", self)
        self._action_new_document.setShortcut(QKeySequence("Ctrl+N"))
        self._action_new_document.triggered.connect(self._on_new_document)
        new_menu.addAction(self._action_new_document)
        
        file_menu.addSeparator()
        
        self._action_open = QAction("&Open...", self)
        self._action_open.setShortcut(QKeySequence.StandardKey.Open)
        self._action_open.triggered.connect(self._on_open)
        file_menu.addAction(self._action_open)
        
        self._action_open_recent = QMenu("Open &Recent", self)
        file_menu.addMenu(self._action_open_recent)
        
        file_menu.addSeparator()
        
        self._action_save = QAction("&Save", self)
        self._action_save.setShortcut(QKeySequence.StandardKey.Save)
        self._action_save.triggered.connect(self._on_save)
        self._action_save.setEnabled(False)
        file_menu.addAction(self._action_save)
        
        self._action_save_as = QAction("Save &As...", self)
        self._action_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self._action_save_as.triggered.connect(self._on_save_as)
        self._action_save_as.setEnabled(False)
        file_menu.addAction(self._action_save_as)
        
        file_menu.addSeparator()
        
        self._action_add_to_collection = QAction("Add to &Collection...", self)
        self._action_add_to_collection.setShortcut(QKeySequence("Ctrl+Shift+C"))
        self._action_add_to_collection.triggered.connect(self._on_add_to_collection)
        self._action_add_to_collection.setEnabled(False)
        file_menu.addAction(self._action_add_to_collection)
        
        file_menu.addSeparator()
        
        self._action_export = QAction("&Export...", self)
        self._action_export.setShortcut(QKeySequence("Ctrl+E"))
        self._action_export.triggered.connect(self._on_export)
        self._action_export.setEnabled(False)
        file_menu.addAction(self._action_export)
        
        self._action_print = QAction("&Print...", self)
        self._action_print.setShortcut(QKeySequence.StandardKey.Print)
        self._action_print.triggered.connect(self._on_print)
        self._action_print.setEnabled(False)
        file_menu.addAction(self._action_print)
        
        file_menu.addSeparator()
        
        self._action_close = QAction("&Close", self)
        self._action_close.setShortcut(QKeySequence.StandardKey.Close)
        self._action_close.triggered.connect(self._on_close_document)
        self._action_close.setEnabled(False)
        file_menu.addAction(self._action_close)
        
        self._action_exit = QAction("E&xit", self)
        self._action_exit.setShortcut(QKeySequence.StandardKey.Quit)
        self._action_exit.triggered.connect(self.close)
        file_menu.addAction(self._action_exit)
        
        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        
        self._action_undo = QAction("&Undo", self)
        self._action_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self._action_undo.triggered.connect(self._on_undo)
        self._action_undo.setEnabled(False)
        edit_menu.addAction(self._action_undo)
        
        self._action_redo = QAction("&Redo", self)
        self._action_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self._action_redo.triggered.connect(self._on_redo)
        self._action_redo.setEnabled(False)
        edit_menu.addAction(self._action_redo)
        
        edit_menu.addSeparator()
        
        self._action_copy = QAction("&Copy", self)
        self._action_copy.setShortcut(QKeySequence.StandardKey.Copy)
        self._action_copy.triggered.connect(self._on_copy)
        edit_menu.addAction(self._action_copy)
        
        self._action_select_all = QAction("Select &All", self)
        self._action_select_all.setShortcut(QKeySequence.StandardKey.SelectAll)
        self._action_select_all.triggered.connect(self._on_select_all)
        edit_menu.addAction(self._action_select_all)
        
        edit_menu.addSeparator()
        
        self._action_find = QAction("&Find...", self)
        self._action_find.setShortcut(QKeySequence.StandardKey.Find)
        self._action_find.triggered.connect(self._on_find)
        edit_menu.addAction(self._action_find)
        
        self._action_find_next = QAction("Find &Next", self)
        self._action_find_next.setShortcut(QKeySequence.StandardKey.FindNext)
        self._action_find_next.triggered.connect(self._on_find_next)
        edit_menu.addAction(self._action_find_next)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        self._action_zoom_in = QAction("Zoom &In", self)
        self._action_zoom_in.setShortcut(QKeySequence.StandardKey.ZoomIn)
        self._action_zoom_in.triggered.connect(self._on_zoom_in)
        view_menu.addAction(self._action_zoom_in)
        
        self._action_zoom_out = QAction("Zoom &Out", self)
        self._action_zoom_out.setShortcut(QKeySequence.StandardKey.ZoomOut)
        self._action_zoom_out.triggered.connect(self._on_zoom_out)
        view_menu.addAction(self._action_zoom_out)
        
        self._action_zoom_reset = QAction("&Reset Zoom", self)
        self._action_zoom_reset.setShortcut(QKeySequence("Ctrl+0"))
        self._action_zoom_reset.triggered.connect(self._on_zoom_reset)
        view_menu.addAction(self._action_zoom_reset)
        
        view_menu.addSeparator()
        
        self._action_fit_width = QAction("Fit &Width", self)
        self._action_fit_width.setShortcut(QKeySequence("Ctrl+Shift+W"))
        self._action_fit_width.triggered.connect(self._on_fit_width)
        view_menu.addAction(self._action_fit_width)
        
        self._action_fit_page = QAction("Fit &Page", self)
        self._action_fit_page.setShortcut(QKeySequence("Ctrl+Shift+P"))
        self._action_fit_page.triggered.connect(self._on_fit_page)
        view_menu.addAction(self._action_fit_page)
        
        view_menu.addSeparator()
        
        self._action_rotate_left = QAction("Rotate &Left", self)
        self._action_rotate_left.setShortcut(QKeySequence("Ctrl+L"))
        self._action_rotate_left.triggered.connect(self._on_rotate_left)
        view_menu.addAction(self._action_rotate_left)
        
        self._action_rotate_right = QAction("Rotate &Right", self)
        self._action_rotate_right.setShortcut(QKeySequence("Ctrl+R"))
        self._action_rotate_right.triggered.connect(self._on_rotate_right)
        view_menu.addAction(self._action_rotate_right)
        
        view_menu.addSeparator()
        
        self._action_single_page = QAction("&Single Page View", self)
        self._action_single_page.setCheckable(True)
        self._action_single_page.setChecked(True)  # Default to single page
        self._action_single_page.triggered.connect(self._on_toggle_single_page)
        view_menu.addAction(self._action_single_page)
        
        self._action_fullscreen = QAction("&Full Screen", self)
        self._action_fullscreen.setShortcut(QKeySequence.StandardKey.FullScreen)
        self._action_fullscreen.setCheckable(True)
        self._action_fullscreen.triggered.connect(self._on_fullscreen)
        view_menu.addAction(self._action_fullscreen)
        
        view_menu.addSeparator()
        
        self._action_show_library = QAction("Show &Library Panel", self)
        self._action_show_library.setCheckable(True)
        self._action_show_library.setChecked(True)
        self._action_show_library.triggered.connect(self._on_toggle_library)
        view_menu.addAction(self._action_show_library)
        
        # Document menu
        document_menu = menubar.addMenu("&Document")
        
        self._action_go_first = QAction("&First Page", self)
        self._action_go_first.setShortcut(QKeySequence.StandardKey.MoveToStartOfDocument)
        self._action_go_first.triggered.connect(self._on_go_first)
        document_menu.addAction(self._action_go_first)
        
        self._action_go_previous = QAction("&Previous Page", self)
        self._action_go_previous.setShortcut(QKeySequence("PgUp"))
        self._action_go_previous.triggered.connect(self._on_go_previous)
        document_menu.addAction(self._action_go_previous)
        
        self._action_go_next = QAction("&Next Page", self)
        self._action_go_next.setShortcut(QKeySequence("PgDown"))
        self._action_go_next.triggered.connect(self._on_go_next)
        document_menu.addAction(self._action_go_next)
        
        self._action_go_last = QAction("&Last Page", self)
        self._action_go_last.setShortcut(QKeySequence.StandardKey.MoveToEndOfDocument)
        self._action_go_last.triggered.connect(self._on_go_last)
        document_menu.addAction(self._action_go_last)
        
        document_menu.addSeparator()
        
        self._action_go_to_page = QAction("&Go to Page...", self)
        self._action_go_to_page.setShortcut(QKeySequence("Ctrl+G"))
        self._action_go_to_page.triggered.connect(self._on_go_to_page)
        document_menu.addAction(self._action_go_to_page)
        
        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        
        self._action_draw_tool = QAction("&Draw", self)
        self._action_draw_tool.setShortcut(QKeySequence("D"))
        self._action_draw_tool.setCheckable(True)
        self._action_draw_tool.setChecked(True)
        self._action_draw_tool.triggered.connect(lambda: self._on_tool_selected("draw"))
        tools_menu.addAction(self._action_draw_tool)
        
        self._action_shape_tool = QAction("S&hape", self)
        self._action_shape_tool.setCheckable(True)
        self._action_shape_tool.triggered.connect(lambda: self._on_tool_selected("rectangle"))
        tools_menu.addAction(self._action_shape_tool)
        
        self._action_eraser_tool = QAction("&Eraser", self)
        self._action_eraser_tool.setShortcut(QKeySequence("E"))
        self._action_eraser_tool.setCheckable(True)
        self._action_eraser_tool.triggered.connect(lambda: self._on_tool_selected("eraser"))
        tools_menu.addAction(self._action_eraser_tool)
        
        tools_menu.addSeparator()
        
        self._action_clear_drawings = QAction("&Clear All Drawings", self)
        self._action_clear_drawings.triggered.connect(self._on_clear_all_drawings)
        tools_menu.addAction(self._action_clear_drawings)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        self._action_about = QAction("&About", self)
        self._action_about.triggered.connect(self._on_about)
        help_menu.addAction(self._action_about)
        
        self._action_about_qt = QAction("About &Qt", self)
        self._action_about_qt.triggered.connect(QApplication.aboutQt)
        help_menu.addAction(self._action_about_qt)
    
    def _create_toolbars(self) -> None:
        """Create the application toolbars."""
        # Main toolbar
        self._main_toolbar = MainToolBar(self)
        self.addToolBar(self._main_toolbar)
        
        # Annotation toolbar (for PDF viewer)
        self._annotation_toolbar = AnnotationToolBar(self)
        self.addToolBar(self._annotation_toolbar)
        
        # Writer toolbar (for document writer)
        self._writer_toolbar = WriterToolBar(self)
        self._writer_toolbar.setVisible(False)  # Hidden by default
        self.addToolBar(self._writer_toolbar)
    
    def _create_statusbar(self) -> None:
        """Create the status bar."""
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        
        # Page indicator
        self._page_label = QLabel("No document")
        self._statusbar.addWidget(self._page_label)
        
        # Zoom indicator
        self._zoom_label = QLabel("100%")
        self._statusbar.addPermanentWidget(self._zoom_label)
    
    def _connect_signals(self) -> None:
        """Connect signals and slots."""
        # Tab widget signals
        self._tab_widget.tabCloseRequested.connect(self._on_tab_close_requested)
        self._tab_widget.currentChanged.connect(self._on_tab_changed)
        
        # Library panel signals
        self._library_panel.document_selected.connect(self._on_library_document_selected)
        
        # Main toolbar signals
        self._main_toolbar.open_clicked.connect(self._on_open)
        self._main_toolbar.save_clicked.connect(self._on_save)
        self._main_toolbar.page_changed.connect(self._on_toolbar_page_changed)
        self._main_toolbar.zoom_changed.connect(self._on_toolbar_zoom_changed)
        
        # Toolbar navigation actions
        self._main_toolbar.get_first_action().triggered.connect(self._on_go_first)
        self._main_toolbar.get_prev_action().triggered.connect(self._on_go_previous)
        self._main_toolbar.get_next_action().triggered.connect(self._on_go_next)
        self._main_toolbar.get_last_action().triggered.connect(self._on_go_last)
        
        # Toolbar zoom actions
        self._main_toolbar.get_zoom_in_action().triggered.connect(self._on_zoom_in)
        self._main_toolbar.get_zoom_out_action().triggered.connect(self._on_zoom_out)
        
        # Toolbar rotation actions
        self._main_toolbar.get_rotate_left_action().triggered.connect(self._on_rotate_left)
        self._main_toolbar.get_rotate_right_action().triggered.connect(self._on_rotate_right)
        
        # Annotation toolbar signals
        self._annotation_toolbar.tool_selected.connect(self._on_tool_selected)
        self._annotation_toolbar.stroke_color_changed.connect(self._on_stroke_color_changed)
        self._annotation_toolbar.fill_color_changed.connect(self._on_fill_color_changed)
        self._annotation_toolbar.stroke_width_changed.connect(self._on_stroke_width_changed)
        self._annotation_toolbar.clear_all_requested.connect(self._on_clear_all_drawings)
        self._annotation_toolbar.drawings_visibility_toggled.connect(self._on_drawings_visibility_toggled)
        self._annotation_toolbar.lens_zoom_changed.connect(self._on_lens_zoom_changed)
        
        # Writer toolbar signals
        self._writer_toolbar.font_family_changed.connect(self._on_writer_font_family_changed)
        self._writer_toolbar.font_size_changed.connect(self._on_writer_font_size_changed)
        self._writer_toolbar.bold_toggled.connect(self._on_writer_bold_toggled)
        self._writer_toolbar.italic_toggled.connect(self._on_writer_italic_toggled)
        self._writer_toolbar.underline_toggled.connect(self._on_writer_underline_toggled)
        self._writer_toolbar.strikethrough_toggled.connect(self._on_writer_strikethrough_toggled)
        self._writer_toolbar.text_color_changed.connect(self._on_writer_text_color_changed)
        self._writer_toolbar.highlight_color_changed.connect(self._on_writer_highlight_color_changed)
        self._writer_toolbar.align_left_clicked.connect(self._on_writer_align_left)
        self._writer_toolbar.align_center_clicked.connect(self._on_writer_align_center)
        self._writer_toolbar.align_right_clicked.connect(self._on_writer_align_right)
        self._writer_toolbar.align_justify_clicked.connect(self._on_writer_align_justify)
        self._writer_toolbar.bullet_list_clicked.connect(self._on_writer_bullet_list)
        self._writer_toolbar.numbered_list_clicked.connect(self._on_writer_numbered_list)
        self._writer_toolbar.indent_increase_clicked.connect(self._on_writer_indent_increase)
        self._writer_toolbar.indent_decrease_clicked.connect(self._on_writer_indent_decrease)
        self._writer_toolbar.insert_image_clicked.connect(self._on_writer_insert_image)
        self._writer_toolbar.insert_table_clicked.connect(self._on_writer_insert_table)
        self._writer_toolbar.insert_equation_clicked.connect(self._on_writer_insert_equation)
        self._writer_toolbar.insert_hr_clicked.connect(self._on_writer_insert_hr)
    
    def _restore_state(self) -> None:
        """Restore window state from settings."""
        geometry = self._settings.value("MainWindow/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        
        state = self._settings.value("MainWindow/state")
        if state:
            self.restoreState(state)
        
        splitter_state = self._settings.value("MainWindow/splitter")
        if splitter_state:
            self._main_splitter.restoreState(splitter_state)
    
    def _save_state(self) -> None:
        """Save window state to settings."""
        self._settings.setValue("MainWindow/geometry", self.saveGeometry())
        self._settings.setValue("MainWindow/state", self.saveState())
        self._settings.setValue("MainWindow/splitter", self._main_splitter.saveState())
    
    # Public methods
    def open_document(self, file_path: Path | str) -> bool:
        """
        Open a PDF document.
        
        Args:
            file_path: Path to the PDF file.
        
        Returns:
            True if document was opened successfully.
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            QMessageBox.warning(
                self,
                "File Not Found",
                f"The file does not exist:\n{file_path}",
            )
            return False
        
        # Check if already open
        for i in range(self._tab_widget.count()):
            viewer = self._tab_widget.widget(i)
            if hasattr(viewer, "file_path") and viewer.file_path == file_path:
                self._tab_widget.setCurrentIndex(i)
                return True
        
        # Create new viewer widget
        viewer = ViewerWidget(file_path, self._services)
        
        # Connect viewer signals BEFORE opening document
        viewer.page_changed.connect(self._on_page_changed)
        viewer.zoom_changed.connect(self._on_zoom_changed)
        
        # Open document
        if not viewer.open_document():
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to open document:\n{file_path}",
            )
            return False
        
        # Add tab
        tab_index = self._tab_widget.addTab(viewer, file_path.name)
        self._tab_widget.setCurrentIndex(tab_index)
        
        # Manually update toolbar with page info (in case signal was missed)
        self._main_toolbar.set_page_count(viewer.page_count)
        self._main_toolbar.set_current_page(viewer.current_page)
        self._main_toolbar.set_zoom_level(viewer.zoom_level)
        self._update_page_label(viewer.current_page + 1, viewer.page_count)
        self._update_zoom_label(viewer.zoom_level)
        
        # Update state
        self._current_document = file_path
        self._update_actions_state()
        
        self.document_opened.emit(str(file_path))
        
        return True
    
    def get_current_viewer(self) -> Optional[ViewerWidget]:
        """Get the currently active viewer widget."""
        widget = self._tab_widget.currentWidget()
        if isinstance(widget, ViewerWidget):
            return widget
        return None
    
    # Slots
    def _on_open(self) -> None:
        """Handle File > Open action."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open PDF",
            "",
            "PDF Files (*.pdf);;All Files (*)",
        )
        
        if file_path:
            self.open_document(file_path)
    
    def _on_save(self) -> None:
        """Handle File > Save action."""
        current_widget = self._tab_widget.currentWidget()
        
        # Check if it's a WriterWidget
        if isinstance(current_widget, WriterWidget):
            current_widget.save_document()
            return
        
        # Otherwise treat as ViewerWidget
        viewer = self.get_current_viewer()
        if viewer:
            viewer.save_annotations()
    
    def _on_save_as(self) -> None:
        """Handle File > Save As action."""
        current_widget = self._tab_widget.currentWidget()
        
        # Check if it's a WriterWidget
        if isinstance(current_widget, WriterWidget):
            current_widget.save_document_as()
            return
        
        # Otherwise treat as ViewerWidget
        viewer = self.get_current_viewer()
        if not viewer:
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save PDF As",
            "",
            "PDF Files (*.pdf)",
        )
        
        if file_path:
            viewer.save_as(file_path)
    
    def _on_add_to_collection(self) -> None:
        """Handle File > Add to Collection action."""
        import shutil
        from ui.library_panel import AddToCollectionDialog
        
        viewer = self.get_current_viewer()
        if not viewer:
            return
        
        collections = self._library_panel.get_collections()
        if not collections:
            QMessageBox.information(
                self,
                "No Collections",
                "Please create a collection first using the Library panel.",
            )
            return
        
        dialog = AddToCollectionDialog(collections, self)
        if dialog.exec():
            data = dialog.get_data()
            collection_name = data["collection"]
            
            collection_path = self._library_panel.get_collection_path(collection_name)
            if collection_path:
                source = viewer.file_path
                dest = Path(collection_path) / source.name
                
                try:
                    if data["copy_file"]:
                        shutil.copy2(source, dest)
                    self._library_panel.refresh()
                    QMessageBox.information(
                        self,
                        "Success",
                        f"Added '{source.name}' to '{collection_name}'.",
                    )
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to add:\\n{e}")
    
    def _on_export(self) -> None:
        """Handle File > Export action."""
        current_widget = self._tab_widget.currentWidget()
        
        # Check if it's a WriterWidget
        if isinstance(current_widget, WriterWidget):
            current_widget.export_to_pdf()
            return
        
        # Otherwise treat as ViewerWidget
        viewer = self.get_current_viewer()
        if viewer:
            viewer.show_export_dialog()
    
    def _on_print(self) -> None:
        """Handle File > Print action."""
        current_widget = self._tab_widget.currentWidget()
        
        # Check if it's a WriterWidget
        if isinstance(current_widget, WriterWidget):
            current_widget.print_document()
            return
        
        # Otherwise treat as ViewerWidget
        viewer = self.get_current_viewer()
        if viewer:
            viewer.print_document()
    
    def _on_close_document(self) -> None:
        """Handle File > Close action."""
        current_index = self._tab_widget.currentIndex()
        if current_index >= 0:
            self._on_tab_close_requested(current_index)
    
    def _on_undo(self) -> None:
        """Handle Edit > Undo action."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.undo()
    
    def _on_redo(self) -> None:
        """Handle Edit > Redo action."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.redo()
    
    def _on_copy(self) -> None:
        """Handle Edit > Copy action."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.copy_selection()
    
    def _on_select_all(self) -> None:
        """Handle Edit > Select All action."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.select_all()
    
    def _on_find(self) -> None:
        """Handle Edit > Find action."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.show_find_dialog()
    
    def _on_find_next(self) -> None:
        """Handle Edit > Find Next action."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.find_next()
    
    def _on_zoom_in(self) -> None:
        """Handle View > Zoom In action."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.zoom_in()
    
    def _on_zoom_out(self) -> None:
        """Handle View > Zoom Out action."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.zoom_out()
    
    def _on_zoom_reset(self) -> None:
        """Handle View > Reset Zoom action."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.zoom_reset()
    
    def _on_fit_width(self) -> None:
        """Handle View > Fit Width action."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.fit_width()
    
    def _on_fit_page(self) -> None:
        """Handle View > Fit Page action."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.fit_page()
    
    def _on_rotate_left(self) -> None:
        """Handle View > Rotate Left action."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.rotate_left()
    
    def _on_rotate_right(self) -> None:
        """Handle View > Rotate Right action."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.rotate_right()
    
    def _on_fullscreen(self, checked: bool) -> None:
        """Handle View > Full Screen action."""
        if checked:
            self.showFullScreen()
        else:
            self.showNormal()
    
    def _on_toggle_library(self, checked: bool) -> None:
        """Handle View > Show Library Panel action."""
        self._library_panel.setVisible(checked)
    
    def _on_toggle_single_page(self, checked: bool) -> None:
        """Handle View > Single Page View action."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.set_view_mode('single' if checked else 'continuous')
    
    def _on_go_first(self) -> None:
        """Handle Document > First Page action."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.go_to_first_page()
    
    def _on_go_previous(self) -> None:
        """Handle Document > Previous Page action."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.go_to_previous_page()
    
    def _on_go_next(self) -> None:
        """Handle Document > Next Page action."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.go_to_next_page()
    
    def _on_go_last(self) -> None:
        """Handle Document > Last Page action."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.go_to_last_page()
    
    def _on_go_to_page(self) -> None:
        """Handle Document > Go to Page action."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.show_go_to_page_dialog()
    
    def _on_tool_selected(self, tool_name: str) -> None:
        """Handle tool selection."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.set_current_tool(tool_name)
    
    def _on_stroke_color_changed(self, color) -> None:
        """Handle stroke color change."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.set_stroke_color(color)
    
    def _on_fill_color_changed(self, color) -> None:
        """Handle fill color change."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.set_fill_color(color)
    
    def _on_stroke_width_changed(self, width: int) -> None:
        """Handle stroke width change."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.set_stroke_width(width)
    
    def _on_clear_all_drawings(self) -> None:
        """Handle clear all drawings request."""
        viewer = self.get_current_viewer()
        if viewer:
            reply = QMessageBox.question(
                self,
                "Clear Drawings",
                "Clear all drawings on the current page?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                viewer.clear_all_drawings()
    
    def _on_drawings_visibility_toggled(self, visible: bool) -> None:
        """Handle drawings visibility toggle."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.set_drawings_visible(visible)
        # Update status bar
        if visible:
            self._statusbar.showMessage("Drawings visible", 2000)
        else:
            self._statusbar.showMessage("Drawings hidden", 2000)
    
    def _on_lens_zoom_changed(self, zoom: float) -> None:
        """Handle lens zoom level change."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.set_lens_zoom(zoom)
        self._statusbar.showMessage(f"Lens zoom: {zoom:.0f}x", 2000)
    
    def _on_about(self) -> None:
        """Handle Help > About action."""
        QMessageBox.about(
            self,
            "About Notepad+++",
            "<h2>Notepad+++</h2>"
            "<p>Version 1.0.0</p>"
            "<p>A professional PDF viewer and annotation application.</p>"
            "<p>Built with Python and PyQt6.</p>",
        )
    
    def _on_tab_close_requested(self, index: int) -> None:
        """Handle tab close request."""
        viewer = self._tab_widget.widget(index)
        
        if isinstance(viewer, ViewerWidget):
            if viewer.has_unsaved_changes():
                reply = QMessageBox.question(
                    self,
                    "Unsaved Changes",
                    f"Save changes to {viewer.file_path.name}?",
                    QMessageBox.StandardButton.Save |
                    QMessageBox.StandardButton.Discard |
                    QMessageBox.StandardButton.Cancel,
                )
                
                if reply == QMessageBox.StandardButton.Save:
                    viewer.save_annotations()
                elif reply == QMessageBox.StandardButton.Cancel:
                    return
            
            file_path = str(viewer.file_path)
            viewer.close_document()
            self.document_closed.emit(file_path)
        
        self._tab_widget.removeTab(index)
        self._update_actions_state()
    
    def _on_tab_changed(self, index: int) -> None:
        """Handle tab change."""
        widget = self._tab_widget.widget(index)
        
        if isinstance(widget, ViewerWidget):
            self._current_document = widget.file_path
            self._update_page_label(widget.current_page + 1, widget.page_count)
            self._update_zoom_label(widget.zoom_level)
            # Show annotation toolbar, hide writer toolbar
            self._annotation_toolbar.setVisible(True)
            self._writer_toolbar.setVisible(False)
        elif isinstance(widget, WriterWidget):
            self._current_document = None
            self._page_label.setText(widget.get_title())
            self._zoom_label.setText("")
            # Show writer toolbar, hide annotation toolbar
            self._annotation_toolbar.setVisible(False)
            self._writer_toolbar.setVisible(True)
            # Update toolbar state
            fmt = widget.get_current_format()
            self._writer_toolbar.update_format_state(**fmt)
        else:
            self._current_document = None
            self._page_label.setText("No document")
            self._zoom_label.setText("100%")
            self._annotation_toolbar.setVisible(True)
            self._writer_toolbar.setVisible(False)
        
        self._update_actions_state()
    
    def _on_library_document_selected(self, file_path: str) -> None:
        """Handle document selection from library."""
        self.open_document(file_path)
    
    def _on_page_changed(self, page: int, total: int) -> None:
        """Handle page change from viewer."""
        self._update_page_label(page + 1, total)
        # Update toolbar page spinner
        self._main_toolbar.set_current_page(page)
        self._main_toolbar.set_page_count(total)
    
    def _on_zoom_changed(self, zoom: float) -> None:
        """Handle zoom change from viewer."""
        self._update_zoom_label(zoom)
        self._main_toolbar.set_zoom_level(zoom)
    
    def _on_toolbar_page_changed(self, page: int) -> None:
        """Handle page change from toolbar spinner."""
        viewer = self.get_current_viewer()
        if viewer:
            viewer.go_to_page(page)
    
    def _on_toolbar_zoom_changed(self, zoom: float) -> None:
        """Handle zoom change from toolbar."""
        viewer = self.get_current_viewer()
        if viewer:
            if zoom == -1:  # Fit Width
                viewer.fit_width()
            elif zoom == -2:  # Fit Page
                viewer.fit_page()
            else:
                viewer.set_zoom(zoom)
    
    def _update_page_label(self, page: int, total: int) -> None:
        """Update the page indicator in status bar."""
        self._page_label.setText(f"Page {page} of {total}")
    
    def _update_zoom_label(self, zoom: float) -> None:
        """Update the zoom indicator in status bar."""
        self._zoom_label.setText(f"{int(zoom * 100)}%")
    
    def _update_actions_state(self) -> None:
        """Update the enabled state of actions based on current state."""
        has_document = self._tab_widget.count() > 0
        viewer = self.get_current_viewer()
        
        self._action_save.setEnabled(has_document)
        self._action_save_as.setEnabled(has_document)
        self._action_add_to_collection.setEnabled(has_document)
        self._action_export.setEnabled(has_document)
        self._action_print.setEnabled(has_document)
        self._action_close.setEnabled(has_document)
        
        # Undo/redo state
        if viewer:
            self._action_undo.setEnabled(viewer.can_undo())
            self._action_redo.setEnabled(viewer.can_redo())
        else:
            self._action_undo.setEnabled(False)
            self._action_redo.setEnabled(False)
    
    # Event handlers
    def closeEvent(self, event) -> None:
        """Handle window close event."""
        # Check for unsaved changes
        for i in range(self._tab_widget.count()):
            widget = self._tab_widget.widget(i)
            if isinstance(widget, ViewerWidget) and widget.has_unsaved_changes():
                reply = QMessageBox.question(
                    self,
                    "Unsaved Changes",
                    "You have unsaved changes. Exit anyway?",
                    QMessageBox.StandardButton.Yes |
                    QMessageBox.StandardButton.No,
                )
                
                if reply == QMessageBox.StandardButton.No:
                    event.ignore()
                    return
                break
            elif isinstance(widget, WriterWidget) and widget.has_changes():
                reply = QMessageBox.question(
                    self,
                    "Unsaved Changes",
                    f"Document '{widget.get_title()}' has unsaved changes. Exit anyway?",
                    QMessageBox.StandardButton.Yes |
                    QMessageBox.StandardButton.No,
                )
                
                if reply == QMessageBox.StandardButton.No:
                    event.ignore()
                    return
        
        # Close all documents
        for i in range(self._tab_widget.count() - 1, -1, -1):
            widget = self._tab_widget.widget(i)
            if isinstance(widget, ViewerWidget):
                widget.close_document()
        
        # Save state
        self._save_state()
        
        event.accept()
    
    # =========================================================================
    # Document Writer Methods
    # =========================================================================
    
    def _on_new_document(self) -> None:
        """Create a new document writer tab."""
        writer = WriterWidget(services=self._services, parent=self)
        writer.document_modified.connect(self._on_writer_document_modified)
        writer.cursor_position_changed.connect(self._on_writer_cursor_changed)
        writer.title_changed.connect(self._on_writer_title_changed)
        
        tab_index = self._tab_widget.addTab(writer, "Untitled Document")
        self._tab_widget.setCurrentIndex(tab_index)
        
        # Show writer toolbar, hide annotation toolbar
        self._annotation_toolbar.setVisible(False)
        self._writer_toolbar.setVisible(True)
        
        writer.focus_editor()
        self._statusbar.showMessage("New document created", 3000)
    
    def get_current_writer(self) -> Optional[WriterWidget]:
        """Get the current writer widget if one is active."""
        widget = self._tab_widget.currentWidget()
        if isinstance(widget, WriterWidget):
            return widget
        return None
    
    def _on_writer_document_modified(self, modified: bool) -> None:
        """Handle writer document modification."""
        writer = self.get_current_writer()
        if writer:
            index = self._tab_widget.indexOf(writer)
            title = writer.get_title()
            if modified:
                self._tab_widget.setTabText(index, f"{title} *")
            else:
                self._tab_widget.setTabText(index, title)
    
    def _on_writer_cursor_changed(self) -> None:
        """Handle writer cursor position change - update toolbar state."""
        writer = self.get_current_writer()
        if writer:
            fmt = writer.get_current_format()
            self._writer_toolbar.update_format_state(**fmt)
    
    def _on_writer_title_changed(self, title: str) -> None:
        """Handle writer title change."""
        writer = self.get_current_writer()
        if writer:
            index = self._tab_widget.indexOf(writer)
            self._tab_widget.setTabText(index, title)
    
    # Writer formatting handlers
    def _on_writer_font_family_changed(self, family: str) -> None:
        writer = self.get_current_writer()
        if writer:
            writer.set_font_family(family)
    
    def _on_writer_font_size_changed(self, size: int) -> None:
        writer = self.get_current_writer()
        if writer:
            writer.set_font_size(size)
    
    def _on_writer_bold_toggled(self) -> None:
        writer = self.get_current_writer()
        if writer:
            writer.toggle_bold()
    
    def _on_writer_italic_toggled(self) -> None:
        writer = self.get_current_writer()
        if writer:
            writer.toggle_italic()
    
    def _on_writer_underline_toggled(self) -> None:
        writer = self.get_current_writer()
        if writer:
            writer.toggle_underline()
    
    def _on_writer_strikethrough_toggled(self) -> None:
        writer = self.get_current_writer()
        if writer:
            writer.toggle_strikethrough()
    
    def _on_writer_text_color_changed(self, color: QColor) -> None:
        writer = self.get_current_writer()
        if writer:
            writer.set_text_color(color)
    
    def _on_writer_highlight_color_changed(self, color: QColor) -> None:
        writer = self.get_current_writer()
        if writer:
            writer.set_highlight_color(color)
    
    def _on_writer_align_left(self) -> None:
        writer = self.get_current_writer()
        if writer:
            writer.set_alignment(Qt.AlignmentFlag.AlignLeft)
    
    def _on_writer_align_center(self) -> None:
        writer = self.get_current_writer()
        if writer:
            writer.set_alignment(Qt.AlignmentFlag.AlignCenter)
    
    def _on_writer_align_right(self) -> None:
        writer = self.get_current_writer()
        if writer:
            writer.set_alignment(Qt.AlignmentFlag.AlignRight)
    
    def _on_writer_align_justify(self) -> None:
        writer = self.get_current_writer()
        if writer:
            writer.set_alignment(Qt.AlignmentFlag.AlignJustify)
    
    def _on_writer_bullet_list(self) -> None:
        writer = self.get_current_writer()
        if writer:
            writer.toggle_bullet_list()
    
    def _on_writer_numbered_list(self) -> None:
        writer = self.get_current_writer()
        if writer:
            writer.toggle_numbered_list()
    
    def _on_writer_indent_increase(self) -> None:
        writer = self.get_current_writer()
        if writer:
            writer.increase_indent()
    
    def _on_writer_indent_decrease(self) -> None:
        writer = self.get_current_writer()
        if writer:
            writer.decrease_indent()
    
    def _on_writer_insert_image(self) -> None:
        writer = self.get_current_writer()
        if writer:
            writer.insert_image()
    
    def _on_writer_insert_table(self) -> None:
        writer = self.get_current_writer()
        if writer:
            writer.insert_table()
    
    def _on_writer_insert_equation(self) -> None:
        writer = self.get_current_writer()
        if writer:
            dialog = EquationDialog(self)
            if dialog.exec() == dialog.DialogCode.Accepted:
                latex = dialog.get_latex()
                if latex:
                    writer.insert_latex_equation(latex)
    
    def _on_writer_insert_hr(self) -> None:
        writer = self.get_current_writer()
        if writer:
            writer.insert_horizontal_rule()

