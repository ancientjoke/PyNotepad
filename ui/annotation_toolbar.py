"""
Annotation Toolbar

Toolbar for annotation and drawing tools.
"""

from __future__ import annotations
from typing import Optional

from PyQt6.QtWidgets import (
    QToolBar,
    QWidget,
    QToolButton,
    QMenu,
    QColorDialog,
    QSpinBox,
    QLabel,
    QWidgetAction,
    QFrame,
    QHBoxLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QAction, QColor, QIcon, QPixmap, QPainter


class ColorButton(QToolButton):
    """Button that displays and allows selecting a color."""
    
    color_changed = pyqtSignal(QColor)
    
    def __init__(self, color: QColor = QColor(255, 0, 0), parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self._color = color
        self._update_icon()
        
        self.clicked.connect(self._on_clicked)
    
    @property
    def color(self) -> QColor:
        """Get the current color."""
        return self._color
    
    @color.setter
    def color(self, color: QColor) -> None:
        """Set the current color."""
        self._color = color
        self._update_icon()
    
    def _update_icon(self) -> None:
        """Update the button icon to show current color."""
        pixmap = QPixmap(24, 24)
        pixmap.fill(self._color)
        
        # Draw border
        painter = QPainter(pixmap)
        painter.setPen(Qt.GlobalColor.black)
        painter.drawRect(0, 0, 23, 23)
        painter.end()
        
        self.setIcon(QIcon(pixmap))
    
    def _on_clicked(self) -> None:
        """Handle button click to show color dialog."""
        color = QColorDialog.getColor(self._color, self, "Select Color")
        if color.isValid():
            self._color = color
            self._update_icon()
            self.color_changed.emit(color)


class AnnotationToolBar(QToolBar):
    """
    Annotation toolbar with drawing and annotation tools.
    
    Signals:
        tool_selected: Emitted when a tool is selected (tool_name)
        stroke_color_changed: Emitted when stroke color changes (QColor)
        fill_color_changed: Emitted when fill color changes (QColor)
        stroke_width_changed: Emitted when stroke width changes (int)
        clear_all_requested: Emitted when clear all is clicked
        drawings_visibility_toggled: Emitted when drawings visibility is toggled (visible)
        lens_zoom_changed: Emitted when lens zoom level changes (zoom_factor)
    """
    
    tool_selected = pyqtSignal(str)
    stroke_color_changed = pyqtSignal(QColor)
    fill_color_changed = pyqtSignal(QColor)
    stroke_width_changed = pyqtSignal(int)
    clear_all_requested = pyqtSignal()
    drawings_visibility_toggled = pyqtSignal(bool)
    lens_zoom_changed = pyqtSignal(float)
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Annotation Toolbar", parent)
        self.setObjectName("AnnotationToolBar")
        
        self.setMovable(True)
        self.setFloatable(False)
        
        self._current_tool = "draw"
        self._tool_actions: dict[str, QAction] = {}
        self._lens_zoom = 3.0
        
        self._setup_tools()
        self._setup_properties()
    
    def _setup_tools(self) -> None:
        """Set up annotation tools."""
        # Freehand draw tool
        self._action_draw = QAction("Draw", self)
        self._action_draw.setCheckable(True)
        self._action_draw.setChecked(True)
        self._action_draw.setToolTip("Freehand drawing (D)")
        self._action_draw.triggered.connect(lambda: self._on_tool_selected("draw"))
        self._tool_actions["draw"] = self._action_draw
        self.addAction(self._action_draw)
        
        # Shape tools with dropdown
        self._shape_button = QToolButton()
        self._shape_button.setText("Shape")
        self._shape_button.setCheckable(True)
        self._shape_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self._shape_button.setToolTip("Shape tools")
        
        shape_menu = QMenu(self._shape_button)
        
        self._action_rect = shape_menu.addAction("Rectangle")
        if self._action_rect:
            self._action_rect.triggered.connect(lambda: self._on_tool_selected("rectangle"))
        
        self._action_ellipse = shape_menu.addAction("Ellipse")
        if self._action_ellipse:
            self._action_ellipse.triggered.connect(lambda: self._on_tool_selected("ellipse"))
        
        self._action_line = shape_menu.addAction("Line")
        if self._action_line:
            self._action_line.triggered.connect(lambda: self._on_tool_selected("line"))
        
        self._action_arrow = shape_menu.addAction("Arrow")
        if self._action_arrow:
            self._action_arrow.triggered.connect(lambda: self._on_tool_selected("arrow"))
        
        self._shape_button.setMenu(shape_menu)
        self._shape_button.clicked.connect(lambda: self._on_tool_selected("rectangle"))
        self.addWidget(self._shape_button)
        
        self._tool_actions["rectangle"] = self._action_rect
        self._tool_actions["ellipse"] = self._action_ellipse
        self._tool_actions["line"] = self._action_line
        self._tool_actions["arrow"] = self._action_arrow
        
        self.addSeparator()
        
        # Eraser tool
        self._action_eraser = QAction("Eraser", self)
        self._action_eraser.setCheckable(True)
        self._action_eraser.setToolTip("Erase drawings")
        self._action_eraser.triggered.connect(lambda: self._on_tool_selected("eraser"))
        self._tool_actions["eraser"] = self._action_eraser
        self.addAction(self._action_eraser)
        
        self.addSeparator()
        
        # Lens/Magnifier tool with zoom options
        self._lens_button = QToolButton()
        self._lens_button.setText("Lens")
        self._lens_button.setCheckable(True)
        self._lens_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self._lens_button.setToolTip("Magnifier lens tool - shows split view with zoom")
        
        lens_menu = QMenu(self._lens_button)
        
        self._action_lens_2x = lens_menu.addAction("2x Zoom")
        if self._action_lens_2x:
            self._action_lens_2x.triggered.connect(lambda: self._on_lens_zoom_selected(2.0))
        
        self._action_lens_3x = lens_menu.addAction("3x Zoom")
        if self._action_lens_3x:
            self._action_lens_3x.triggered.connect(lambda: self._on_lens_zoom_selected(3.0))
        
        self._action_lens_4x = lens_menu.addAction("4x Zoom")
        if self._action_lens_4x:
            self._action_lens_4x.triggered.connect(lambda: self._on_lens_zoom_selected(4.0))
        
        self._action_lens_5x = lens_menu.addAction("5x Zoom")
        if self._action_lens_5x:
            self._action_lens_5x.triggered.connect(lambda: self._on_lens_zoom_selected(5.0))
        
        self._action_lens_8x = lens_menu.addAction("8x Zoom")
        if self._action_lens_8x:
            self._action_lens_8x.triggered.connect(lambda: self._on_lens_zoom_selected(8.0))
        
        self._lens_button.setMenu(lens_menu)
        self._lens_button.clicked.connect(lambda: self._on_tool_selected("lens"))
        self.addWidget(self._lens_button)
        
        self._tool_actions["lens"] = None  # Special handling for lens button
        self._lens_zoom = 3.0  # Default lens zoom
    
    def _setup_properties(self) -> None:
        """Set up property controls."""
        self.addSeparator()
        
        # Stroke color
        stroke_label = QLabel("Stroke:")
        self.addWidget(stroke_label)
        
        self._stroke_color_btn = ColorButton(QColor(255, 0, 0))
        self._stroke_color_btn.setToolTip("Stroke color")
        self._stroke_color_btn.color_changed.connect(self.stroke_color_changed.emit)
        self.addWidget(self._stroke_color_btn)
        
        # Fill color
        fill_label = QLabel("Fill:")
        self.addWidget(fill_label)
        
        self._fill_color_btn = ColorButton(QColor(255, 255, 0, 128))
        self._fill_color_btn.setToolTip("Fill color")
        self._fill_color_btn.color_changed.connect(self.fill_color_changed.emit)
        self.addWidget(self._fill_color_btn)
        
        # Stroke width
        width_label = QLabel("Width:")
        self.addWidget(width_label)
        
        self._stroke_width_spin = QSpinBox()
        self._stroke_width_spin.setRange(1, 20)
        self._stroke_width_spin.setValue(2)
        self._stroke_width_spin.setToolTip("Stroke width")
        self._stroke_width_spin.valueChanged.connect(self.stroke_width_changed.emit)
        self.addWidget(self._stroke_width_spin)
        
        self.addSeparator()
        
        # Clear all button
        self._action_clear = QAction("Clear All", self)
        self._action_clear.setToolTip("Clear all drawings on current page")
        self._action_clear.triggered.connect(self.clear_all_requested.emit)
        self.addAction(self._action_clear)
        
        self.addSeparator()
        
        # Show/Hide drawings toggle
        self._action_toggle_visibility = QAction("Show Drawings", self)
        self._action_toggle_visibility.setCheckable(True)
        self._action_toggle_visibility.setChecked(True)
        self._action_toggle_visibility.setToolTip("Show or hide all drawings")
        self._action_toggle_visibility.triggered.connect(self._on_toggle_visibility)
        self.addAction(self._action_toggle_visibility)
        
        self.addSeparator()
        
        # Lens enable/disable toggle
        self._action_lens_enabled = QAction("Lens Enabled", self)
        self._action_lens_enabled.setCheckable(True)
        self._action_lens_enabled.setChecked(True)
        self._action_lens_enabled.setToolTip("Enable or disable lens tool")
        self._action_lens_enabled.triggered.connect(self._on_lens_enabled_toggled)
        self.addAction(self._action_lens_enabled)
    
    def _on_tool_selected(self, tool_name: str) -> None:
        """Handle tool selection."""
        # Uncheck all tools
        for action in self._tool_actions.values():
            if action:
                action.setChecked(False)
        self._shape_button.setChecked(False)
        self._lens_button.setChecked(False)
        
        # Check selected tool
        if tool_name in self._tool_actions and self._tool_actions[tool_name]:
            self._tool_actions[tool_name].setChecked(True)
        
        if tool_name in ("rectangle", "ellipse", "line", "arrow"):
            self._shape_button.setChecked(True)
        
        if tool_name == "lens":
            self._lens_button.setChecked(True)
        
        self._current_tool = tool_name
        self.tool_selected.emit(tool_name)
    
    def _on_lens_zoom_selected(self, zoom: float) -> None:
        """Handle lens zoom level selection."""
        self._lens_zoom = zoom
        self._lens_button.setText(f"Lens {int(zoom)}x")
        self._on_tool_selected("lens")
        self.lens_zoom_changed.emit(zoom)
    
    def get_lens_zoom(self) -> float:
        """Get current lens zoom level."""
        return self._lens_zoom
    
    def _on_toggle_visibility(self, checked: bool) -> None:
        """Handle drawings visibility toggle."""
        if checked:
            self._action_toggle_visibility.setText("Show Drawings")
        else:
            self._action_toggle_visibility.setText("Hide Drawings")
        self.drawings_visibility_toggled.emit(checked)
    
    def _on_lens_enabled_toggled(self, checked: bool) -> None:
        """Handle lens enabled toggle."""
        self._lens_button.setEnabled(checked)
        if not checked and self._lens_button.isChecked():
            # Switch to draw tool if lens was active
            self._on_tool_selected("draw")
            self.tool_selected.emit("draw")
    
    def set_drawings_visible(self, visible: bool) -> None:
        """Set drawings visibility externally."""
        self._action_toggle_visibility.setChecked(visible)
        if visible:
            self._action_toggle_visibility.setText("Show Drawings")
        else:
            self._action_toggle_visibility.setText("Hide Drawings")
    
    @property
    def current_tool(self) -> str:
        """Get the currently selected tool."""
        return self._current_tool
    
    @property
    def stroke_color(self) -> QColor:
        """Get the current stroke color."""
        return self._stroke_color_btn.color
    
    @stroke_color.setter
    def stroke_color(self, color: QColor) -> None:
        """Set the stroke color."""
        self._stroke_color_btn.color = color
    
    @property
    def fill_color(self) -> QColor:
        """Get the current fill color."""
        return self._fill_color_btn.color
    
    @fill_color.setter
    def fill_color(self, color: QColor) -> None:
        """Set the fill color."""
        self._fill_color_btn.color = color
    
    @property
    def stroke_width(self) -> int:
        """Get the current stroke width."""
        return self._stroke_width_spin.value()
    
    @stroke_width.setter
    def stroke_width(self, width: int) -> None:
        """Set the stroke width."""
        self._stroke_width_spin.setValue(width)
    
    def set_tool(self, tool_name: str) -> None:
        """Programmatically select a tool."""
        self._on_tool_selected(tool_name)
