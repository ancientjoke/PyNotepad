"""
Writer Toolbar

Formatting toolbar for the document writer with font controls,
text formatting, alignment, lists, and insert options.
"""

from __future__ import annotations
from typing import Optional, List

from PyQt6.QtWidgets import (
    QToolBar,
    QWidget,
    QComboBox,
    QSpinBox,
    QToolButton,
    QMenu,
    QColorDialog,
    QInputDialog,
    QWidgetAction,
    QLabel,
    QHBoxLayout,
    QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QAction, QIcon, QPixmap, QPainter


class ColorButton(QToolButton):
    """Button that shows and lets user pick a color."""
    
    color_changed = pyqtSignal(QColor)
    
    def __init__(self, initial_color: QColor = QColor(0, 0, 0), parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._color = initial_color
        self.setFixedSize(28, 28)
        self.clicked.connect(self._pick_color)
        self._update_icon()
    
    @property
    def color(self) -> QColor:
        return self._color
    
    @color.setter
    def color(self, color: QColor) -> None:
        self._color = color
        self._update_icon()
    
    def _update_icon(self) -> None:
        pixmap = QPixmap(20, 20)
        pixmap.fill(self._color)
        
        # Draw border
        painter = QPainter(pixmap)
        painter.setPen(QColor(128, 128, 128))
        painter.drawRect(0, 0, 19, 19)
        painter.end()
        
        self.setIcon(QIcon(pixmap))
    
    def _pick_color(self) -> None:
        color = QColorDialog.getColor(self._color, self, "Select Color")
        if color.isValid():
            self._color = color
            self._update_icon()
            self.color_changed.emit(color)


class WriterToolBar(QToolBar):
    """
    Formatting toolbar for the document writer.
    
    Signals:
        font_family_changed: (str) Font family changed
        font_size_changed: (int) Font size changed
        bold_toggled: Bold button clicked
        italic_toggled: Italic button clicked
        underline_toggled: Underline button clicked
        strikethrough_toggled: Strikethrough button clicked
        text_color_changed: (QColor) Text color changed
        highlight_color_changed: (QColor) Highlight color changed
        align_left_clicked: Left align clicked
        align_center_clicked: Center align clicked
        align_right_clicked: Right align clicked
        align_justify_clicked: Justify clicked
        bullet_list_clicked: Bullet list clicked
        numbered_list_clicked: Numbered list clicked
        indent_increase_clicked: Increase indent clicked
        indent_decrease_clicked: Decrease indent clicked
        insert_image_clicked: Insert image clicked
        insert_table_clicked: Insert table clicked
        insert_equation_clicked: Insert equation clicked
        insert_link_clicked: Insert link clicked
        insert_hr_clicked: Insert horizontal rule clicked
    """
    
    # Font signals
    font_family_changed = pyqtSignal(str)
    font_size_changed = pyqtSignal(int)
    
    # Format signals
    bold_toggled = pyqtSignal()
    italic_toggled = pyqtSignal()
    underline_toggled = pyqtSignal()
    strikethrough_toggled = pyqtSignal()
    
    # Color signals
    text_color_changed = pyqtSignal(QColor)
    highlight_color_changed = pyqtSignal(QColor)
    
    # Alignment signals
    align_left_clicked = pyqtSignal()
    align_center_clicked = pyqtSignal()
    align_right_clicked = pyqtSignal()
    align_justify_clicked = pyqtSignal()
    
    # List signals
    bullet_list_clicked = pyqtSignal()
    numbered_list_clicked = pyqtSignal()
    indent_increase_clicked = pyqtSignal()
    indent_decrease_clicked = pyqtSignal()
    
    # Insert signals
    insert_image_clicked = pyqtSignal()
    insert_table_clicked = pyqtSignal()
    insert_equation_clicked = pyqtSignal()
    insert_link_clicked = pyqtSignal()
    insert_hr_clicked = pyqtSignal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Writer", parent)
        self.setObjectName("WriterToolBar")
        
        self.setMovable(False)
        self.setIconSize(QSize(16, 16))
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up toolbar UI."""
        
        # =====================================================================
        # Font Family
        # =====================================================================
        self._font_combo = QComboBox()
        self._font_combo.setMinimumWidth(150)
        self._font_combo.setEditable(True)
        
        # Common fonts
        fonts = [
            "Arial", "Times New Roman", "Calibri", "Cambria", "Georgia",
            "Verdana", "Tahoma", "Trebuchet MS", "Comic Sans MS",
            "Courier New", "Consolas", "Lucida Console",
        ]
        self._font_combo.addItems(fonts)
        self._font_combo.setCurrentText("Arial")
        self._font_combo.currentTextChanged.connect(self.font_family_changed.emit)
        self.addWidget(self._font_combo)
        
        # =====================================================================
        # Font Size
        # =====================================================================
        self._size_combo = QComboBox()
        self._size_combo.setMinimumWidth(60)
        self._size_combo.setEditable(True)
        
        sizes = ["8", "9", "10", "11", "12", "14", "16", "18", "20", "24", "28", "32", "36", "48", "72"]
        self._size_combo.addItems(sizes)
        self._size_combo.setCurrentText("11")
        self._size_combo.currentTextChanged.connect(self._on_size_changed)
        self.addWidget(self._size_combo)
        
        self.addSeparator()
        
        # =====================================================================
        # Text Formatting
        # =====================================================================
        self._bold_action = QAction("Bold", self)
        self._bold_action.setCheckable(True)
        self._bold_action.setShortcut("Ctrl+B")
        self._bold_action.setToolTip("Bold (Ctrl+B)")
        self._bold_action.triggered.connect(self.bold_toggled.emit)
        self.addAction(self._bold_action)
        
        self._italic_action = QAction("Italic", self)
        self._italic_action.setCheckable(True)
        self._italic_action.setShortcut("Ctrl+I")
        self._italic_action.setToolTip("Italic (Ctrl+I)")
        self._italic_action.triggered.connect(self.italic_toggled.emit)
        self.addAction(self._italic_action)
        
        self._underline_action = QAction("Underline", self)
        self._underline_action.setCheckable(True)
        self._underline_action.setShortcut("Ctrl+U")
        self._underline_action.setToolTip("Underline (Ctrl+U)")
        self._underline_action.triggered.connect(self.underline_toggled.emit)
        self.addAction(self._underline_action)
        
        self._strikethrough_action = QAction("Strikethrough", self)
        self._strikethrough_action.setCheckable(True)
        self._strikethrough_action.setToolTip("Strikethrough")
        self._strikethrough_action.triggered.connect(self.strikethrough_toggled.emit)
        self.addAction(self._strikethrough_action)
        
        self.addSeparator()
        
        # =====================================================================
        # Colors
        # =====================================================================
        self._text_color_btn = ColorButton(QColor(0, 0, 0))
        self._text_color_btn.setToolTip("Text Color")
        self._text_color_btn.color_changed.connect(self.text_color_changed.emit)
        self.addWidget(self._text_color_btn)
        
        self._highlight_btn = ColorButton(QColor(255, 255, 0))
        self._highlight_btn.setToolTip("Highlight Color")
        self._highlight_btn.color_changed.connect(self.highlight_color_changed.emit)
        self.addWidget(self._highlight_btn)
        
        self.addSeparator()
        
        # =====================================================================
        # Alignment
        # =====================================================================
        self._align_left_action = QAction("Align Left", self)
        self._align_left_action.setCheckable(True)
        self._align_left_action.setChecked(True)
        self._align_left_action.setToolTip("Align Left")
        self._align_left_action.triggered.connect(self._on_align_left)
        self.addAction(self._align_left_action)
        
        self._align_center_action = QAction("Center", self)
        self._align_center_action.setCheckable(True)
        self._align_center_action.setToolTip("Center")
        self._align_center_action.triggered.connect(self._on_align_center)
        self.addAction(self._align_center_action)
        
        self._align_right_action = QAction("Align Right", self)
        self._align_right_action.setCheckable(True)
        self._align_right_action.setToolTip("Align Right")
        self._align_right_action.triggered.connect(self._on_align_right)
        self.addAction(self._align_right_action)
        
        self._align_justify_action = QAction("Justify", self)
        self._align_justify_action.setCheckable(True)
        self._align_justify_action.setToolTip("Justify")
        self._align_justify_action.triggered.connect(self._on_align_justify)
        self.addAction(self._align_justify_action)
        
        self.addSeparator()
        
        # =====================================================================
        # Lists
        # =====================================================================
        self._bullet_list_action = QAction("Bullet List", self)
        self._bullet_list_action.setToolTip("Bullet List")
        self._bullet_list_action.triggered.connect(self.bullet_list_clicked.emit)
        self.addAction(self._bullet_list_action)
        
        self._numbered_list_action = QAction("Numbered List", self)
        self._numbered_list_action.setToolTip("Numbered List")
        self._numbered_list_action.triggered.connect(self.numbered_list_clicked.emit)
        self.addAction(self._numbered_list_action)
        
        self._indent_decrease_action = QAction("Decrease Indent", self)
        self._indent_decrease_action.setToolTip("Decrease Indent")
        self._indent_decrease_action.triggered.connect(self.indent_decrease_clicked.emit)
        self.addAction(self._indent_decrease_action)
        
        self._indent_increase_action = QAction("Increase Indent", self)
        self._indent_increase_action.setToolTip("Increase Indent")
        self._indent_increase_action.triggered.connect(self.indent_increase_clicked.emit)
        self.addAction(self._indent_increase_action)
        
        self.addSeparator()
        
        # =====================================================================
        # Insert Menu
        # =====================================================================
        self._insert_button = QToolButton()
        self._insert_button.setText("Insert")
        self._insert_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        insert_menu = QMenu(self._insert_button)
        
        insert_image_action = insert_menu.addAction("Image...")
        insert_image_action.triggered.connect(self.insert_image_clicked.emit)
        
        insert_table_action = insert_menu.addAction("Table...")
        insert_table_action.triggered.connect(self.insert_table_clicked.emit)
        
        insert_menu.addSeparator()
        
        insert_equation_action = insert_menu.addAction("Equation (LaTeX)...")
        insert_equation_action.triggered.connect(self.insert_equation_clicked.emit)
        
        insert_menu.addSeparator()
        
        insert_hr_action = insert_menu.addAction("Horizontal Line")
        insert_hr_action.triggered.connect(self.insert_hr_clicked.emit)
        
        self._insert_button.setMenu(insert_menu)
        self.addWidget(self._insert_button)
    
    def _on_size_changed(self, text: str) -> None:
        """Handle font size change."""
        try:
            size = int(text)
            if 1 <= size <= 200:
                self.font_size_changed.emit(size)
        except ValueError:
            pass
    
    def _on_align_left(self) -> None:
        """Handle left align."""
        self._update_alignment_buttons("left")
        self.align_left_clicked.emit()
    
    def _on_align_center(self) -> None:
        """Handle center align."""
        self._update_alignment_buttons("center")
        self.align_center_clicked.emit()
    
    def _on_align_right(self) -> None:
        """Handle right align."""
        self._update_alignment_buttons("right")
        self.align_right_clicked.emit()
    
    def _on_align_justify(self) -> None:
        """Handle justify."""
        self._update_alignment_buttons("justify")
        self.align_justify_clicked.emit()
    
    def _update_alignment_buttons(self, active: str) -> None:
        """Update alignment button states."""
        self._align_left_action.setChecked(active == "left")
        self._align_center_action.setChecked(active == "center")
        self._align_right_action.setChecked(active == "right")
        self._align_justify_action.setChecked(active == "justify")
    
    # =========================================================================
    # Public Methods for State Updates
    # =========================================================================
    
    def update_format_state(
        self,
        font_family: str = "",
        font_size: int = 11,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        strikethrough: bool = False,
        text_color: Optional[QColor] = None,
        highlight_color: Optional[QColor] = None,
        alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft,
    ) -> None:
        """Update toolbar state to match current text format."""
        # Block signals to avoid triggering changes
        self._font_combo.blockSignals(True)
        self._size_combo.blockSignals(True)
        
        if font_family:
            self._font_combo.setCurrentText(font_family)
        if font_size > 0:
            self._size_combo.setCurrentText(str(font_size))
        
        self._font_combo.blockSignals(False)
        self._size_combo.blockSignals(False)
        
        self._bold_action.setChecked(bold)
        self._italic_action.setChecked(italic)
        self._underline_action.setChecked(underline)
        self._strikethrough_action.setChecked(strikethrough)
        
        if text_color:
            self._text_color_btn.color = text_color
        if highlight_color:
            self._highlight_btn.color = highlight_color
        
        # Update alignment
        if alignment & Qt.AlignmentFlag.AlignLeft:
            self._update_alignment_buttons("left")
        elif alignment & Qt.AlignmentFlag.AlignHCenter:
            self._update_alignment_buttons("center")
        elif alignment & Qt.AlignmentFlag.AlignRight:
            self._update_alignment_buttons("right")
        elif alignment & Qt.AlignmentFlag.AlignJustify:
            self._update_alignment_buttons("justify")
    
    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable all toolbar controls."""
        for action in self.actions():
            action.setEnabled(enabled)
        self._font_combo.setEnabled(enabled)
        self._size_combo.setEnabled(enabled)
        self._text_color_btn.setEnabled(enabled)
        self._highlight_btn.setEnabled(enabled)
        self._insert_button.setEnabled(enabled)
