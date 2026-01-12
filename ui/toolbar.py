"""
Main Toolbar

Primary application toolbar with common actions.
"""

from __future__ import annotations
from typing import Optional

from PyQt6.QtWidgets import (
    QToolBar,
    QWidget,
    QSpinBox,
    QComboBox,
    QLabel,
    QLineEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence


class MainToolBar(QToolBar):
    """
    Main application toolbar.
    
    Signals:
        open_clicked: Emitted when open button is clicked
        save_clicked: Emitted when save button is clicked
        page_changed: Emitted when page number is changed
        zoom_changed: Emitted when zoom level is changed
    """
    
    open_clicked = pyqtSignal()
    save_clicked = pyqtSignal()
    page_changed = pyqtSignal(int)
    zoom_changed = pyqtSignal(float)
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Main Toolbar", parent)
        self.setObjectName("MainToolBar")
        
        self.setMovable(True)
        self.setFloatable(False)
        
        self._setup_actions()
        self._setup_widgets()
    
    def _setup_actions(self) -> None:
        """Set up toolbar actions."""
        # File actions
        self._action_open = QAction("Open", self)
        self._action_open.setShortcut(QKeySequence.StandardKey.Open)
        self._action_open.setToolTip("Open PDF file (Ctrl+O)")
        self._action_open.triggered.connect(self.open_clicked.emit)
        self.addAction(self._action_open)
        
        self._action_save = QAction("Save", self)
        self._action_save.setShortcut(QKeySequence.StandardKey.Save)
        self._action_save.setToolTip("Save annotations (Ctrl+S)")
        self._action_save.triggered.connect(self.save_clicked.emit)
        self.addAction(self._action_save)
        
        self.addSeparator()
        
        # Navigation actions
        self._action_first = QAction("First", self)
        self._action_first.setToolTip("Go to first page")
        self.addAction(self._action_first)
        
        self._action_prev = QAction("Previous", self)
        self._action_prev.setToolTip("Go to previous page")
        self.addAction(self._action_prev)
    
    def _setup_widgets(self) -> None:
        """Set up toolbar widgets."""
        # Page navigation
        self._page_spin = QSpinBox()
        self._page_spin.setMinimum(1)
        self._page_spin.setMaximum(1)
        self._page_spin.setToolTip("Current page")
        self._page_spin.valueChanged.connect(lambda v: self.page_changed.emit(v - 1))
        self.addWidget(self._page_spin)
        
        self._page_label = QLabel(" / 1")
        self.addWidget(self._page_label)
        
        # Next/Last actions
        self._action_next = QAction("Next", self)
        self._action_next.setToolTip("Go to next page")
        self.addAction(self._action_next)
        
        self._action_last = QAction("Last", self)
        self._action_last.setToolTip("Go to last page")
        self.addAction(self._action_last)
        
        self.addSeparator()
        
        # Zoom controls
        self._action_zoom_out = QAction("-", self)
        self._action_zoom_out.setToolTip("Zoom out")
        self.addAction(self._action_zoom_out)
        
        self._zoom_combo = QComboBox()
        self._zoom_combo.setEditable(True)
        self._zoom_combo.addItems([
            "50%", "75%", "100%", "125%", "150%", "200%", "300%", "400%",
            "Fit Width", "Fit Page", "Actual Size"
        ])
        self._zoom_combo.setCurrentText("100%")
        self._zoom_combo.setToolTip("Zoom level")
        self._zoom_combo.setMinimumWidth(100)
        self._zoom_combo.currentTextChanged.connect(self._on_zoom_changed)
        self.addWidget(self._zoom_combo)
        
        self._action_zoom_in = QAction("+", self)
        self._action_zoom_in.setToolTip("Zoom in")
        self.addAction(self._action_zoom_in)
        
        self.addSeparator()
        
        # Rotation actions
        self._action_rotate_left = QAction("Rotate Left", self)
        self._action_rotate_left.setToolTip("Rotate left")
        self.addAction(self._action_rotate_left)
        
        self._action_rotate_right = QAction("Rotate Right", self)
        self._action_rotate_right.setToolTip("Rotate right")
        self.addAction(self._action_rotate_right)
        
        self.addSeparator()
        
        # Search
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search...")
        self._search_edit.setMaximumWidth(200)
        self.addWidget(self._search_edit)
    
    def _on_zoom_changed(self, text: str) -> None:
        """Handle zoom combo box change."""
        text = text.strip().replace("%", "")
        
        if text == "Fit Width":
            self.zoom_changed.emit(-1)  # Special value for fit width
        elif text == "Fit Page":
            self.zoom_changed.emit(-2)  # Special value for fit page
        elif text == "Actual Size":
            self.zoom_changed.emit(1.0)
        else:
            try:
                zoom = float(text) / 100
                self.zoom_changed.emit(zoom)
            except ValueError:
                pass
    
    def set_page_count(self, count: int) -> None:
        """Set the total page count."""
        self._page_spin.setMaximum(count)
        self._page_label.setText(f" / {count}")
    
    def set_current_page(self, page: int) -> None:
        """Set the current page (0-based)."""
        self._page_spin.blockSignals(True)
        self._page_spin.setValue(page + 1)
        self._page_spin.blockSignals(False)
    
    def set_zoom_level(self, zoom: float) -> None:
        """Set the current zoom level."""
        self._zoom_combo.blockSignals(True)
        self._zoom_combo.setCurrentText(f"{int(zoom * 100)}%")
        self._zoom_combo.blockSignals(False)
    
    def get_first_action(self) -> QAction:
        """Get the first page action."""
        return self._action_first
    
    def get_prev_action(self) -> QAction:
        """Get the previous page action."""
        return self._action_prev
    
    def get_next_action(self) -> QAction:
        """Get the next page action."""
        return self._action_next
    
    def get_last_action(self) -> QAction:
        """Get the last page action."""
        return self._action_last
    
    def get_zoom_in_action(self) -> QAction:
        """Get the zoom in action."""
        return self._action_zoom_in
    
    def get_zoom_out_action(self) -> QAction:
        """Get the zoom out action."""
        return self._action_zoom_out
    
    def get_rotate_left_action(self) -> QAction:
        """Get the rotate left action."""
        return self._action_rotate_left
    
    def get_rotate_right_action(self) -> QAction:
        """Get the rotate right action."""
        return self._action_rotate_right
