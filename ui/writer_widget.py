"""
Writer Widget

A rich text document editor similar to Google Docs with support for
formatting, images, tables, and LaTeX equations.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict, Any, List
import json
import base64

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QScrollArea,
    QFrame,
    QLabel,
    QApplication,
    QMessageBox,
    QFileDialog,
    QInputDialog,
    QColorDialog,
    QFontDialog,
)
from PyQt6.QtCore import Qt, QPoint, QSize, pyqtSignal, QTimer, QMarginsF
from PyQt6.QtGui import (
    QFont,
    QColor,
    QTextCursor,
    QTextCharFormat,
    QTextBlockFormat,
    QTextListFormat,
    QTextTableFormat,
    QTextFrameFormat,
    QTextImageFormat,
    QTextDocument,
    QImage,
    QKeySequence,
    QAction,
    QPainter,
    QPageSize,
    QPageLayout,
)
from PyQt6.QtPrintSupport import QPrinter


class WriterWidget(QWidget):
    """
    Rich text document editor widget.
    
    Signals:
        document_modified: Emitted when document content changes
        cursor_position_changed: Emitted when cursor moves (for toolbar updates)
        title_changed: Emitted when document title changes
    """
    
    document_modified = pyqtSignal(bool)
    cursor_position_changed = pyqtSignal()
    title_changed = pyqtSignal(str)
    
    def __init__(
        self,
        file_path: Optional[Path] = None,
        services: Optional[Dict[str, Any]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        
        self._file_path = file_path
        self._services = services or {}
        self._document_title = "Untitled Document"
        self._has_changes = False
        self._autosave_enabled = True
        self._autosave_interval = 30000  # 30 seconds
        
        self._setup_ui()
        self._setup_autosave()
        self._connect_signals()
        
        if file_path and file_path.exists():
            self._load_document(file_path)
    
    def _setup_ui(self) -> None:
        """Set up the editor UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Document container with page-like appearance
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #e0e0e0;
                border: none;
            }
        """)
        
        # Page container
        page_container = QWidget()
        page_layout = QVBoxLayout(page_container)
        page_layout.setContentsMargins(40, 40, 40, 40)
        page_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        
        # The actual text editor (styled like a page)
        self._editor = QTextEdit()
        self._editor.setMinimumWidth(816)  # ~8.5 inches at 96 DPI
        self._editor.setMinimumHeight(1056)  # ~11 inches at 96 DPI
        self._editor.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #cccccc;
                padding: 72px;  /* 0.75 inch margins */
                font-family: 'Arial', sans-serif;
                font-size: 11pt;
            }
        """)
        
        # Set default font
        default_font = QFont("Arial", 11)
        self._editor.setFont(default_font)
        
        # Enable rich text
        self._editor.setAcceptRichText(True)
        
        page_layout.addWidget(self._editor)
        page_layout.addStretch()
        
        self._scroll_area.setWidget(page_container)
        layout.addWidget(self._scroll_area)
    
    def _setup_autosave(self) -> None:
        """Set up autosave timer."""
        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._autosave)
        if self._autosave_enabled:
            self._autosave_timer.start(self._autosave_interval)
    
    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self._editor.textChanged.connect(self._on_text_changed)
        self._editor.cursorPositionChanged.connect(self._on_cursor_changed)
    
    def _on_text_changed(self) -> None:
        """Handle text changes."""
        if not self._has_changes:
            self._has_changes = True
            self.document_modified.emit(True)
    
    def _on_cursor_changed(self) -> None:
        """Handle cursor position changes."""
        self.cursor_position_changed.emit()
    
    def _autosave(self) -> None:
        """Auto-save the document if it has changes."""
        if self._has_changes and self._file_path:
            self.save_document()
    
    # =========================================================================
    # Document Operations
    # =========================================================================
    
    def new_document(self) -> None:
        """Create a new empty document."""
        self._editor.clear()
        self._file_path = None
        self._document_title = "Untitled Document"
        self._has_changes = False
        self.title_changed.emit(self._document_title)
        self.document_modified.emit(False)
    
    def _load_document(self, file_path: Path) -> bool:
        """Load a document from file."""
        try:
            suffix = file_path.suffix.lower()
            
            if suffix == ".npp":
                # Native format (JSON with embedded content)
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._editor.setHtml(data.get("content", ""))
                self._document_title = data.get("title", file_path.stem)
            elif suffix == ".html" or suffix == ".htm":
                with open(file_path, "r", encoding="utf-8") as f:
                    self._editor.setHtml(f.read())
                self._document_title = file_path.stem
            elif suffix == ".txt":
                with open(file_path, "r", encoding="utf-8") as f:
                    self._editor.setPlainText(f.read())
                self._document_title = file_path.stem
            else:
                # Try to load as plain text
                with open(file_path, "r", encoding="utf-8") as f:
                    self._editor.setPlainText(f.read())
                self._document_title = file_path.stem
            
            self._file_path = file_path
            self._has_changes = False
            self.title_changed.emit(self._document_title)
            return True
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Loading Document",
                f"Failed to load document:\n{e}"
            )
            return False
    
    def save_document(self) -> bool:
        """Save the current document."""
        if not self._file_path:
            return self.save_document_as()
        
        try:
            suffix = self._file_path.suffix.lower()
            
            if suffix == ".npp":
                # Native format
                data = {
                    "title": self._document_title,
                    "content": self._editor.toHtml(),
                    "version": "1.0",
                }
                with open(self._file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            elif suffix == ".html" or suffix == ".htm":
                with open(self._file_path, "w", encoding="utf-8") as f:
                    f.write(self._editor.toHtml())
            elif suffix == ".txt":
                with open(self._file_path, "w", encoding="utf-8") as f:
                    f.write(self._editor.toPlainText())
            else:
                # Default to HTML
                with open(self._file_path, "w", encoding="utf-8") as f:
                    f.write(self._editor.toHtml())
            
            self._has_changes = False
            self.document_modified.emit(False)
            return True
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Saving Document",
                f"Failed to save document:\n{e}"
            )
            return False
    
    def save_document_as(self) -> bool:
        """Save document with a new name."""
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Document As",
            self._document_title,
            "Notepad+++ Document (*.npp);;HTML Document (*.html);;Plain Text (*.txt);;All Files (*)"
        )
        
        if not file_path:
            return False
        
        self._file_path = Path(file_path)
        self._document_title = self._file_path.stem
        self.title_changed.emit(self._document_title)
        return self.save_document()
    
    def export_to_pdf(self) -> bool:
        """Export document to PDF."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export to PDF",
            self._document_title + ".pdf",
            "PDF Files (*.pdf)"
        )
        
        if not file_path:
            return False
        
        try:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(file_path)
            
            # Set page size to Letter
            page_layout = QPageLayout(
                QPageSize(QPageSize.PageSizeId.Letter),
                QPageLayout.Orientation.Portrait,
                QMarginsF(72, 72, 72, 72)  # 1 inch margins
            )
            printer.setPageLayout(page_layout)
            
            self._editor.document().print(printer)
            
            QMessageBox.information(
                self,
                "Export Complete",
                f"Document exported to:\n{file_path}"
            )
            return True
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export PDF:\n{e}"
            )
            return False
    
    def print_document(self) -> None:
        """Print the document."""
        from PyQt6.QtPrintSupport import QPrintDialog
        
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        
        # Set page size to Letter
        page_layout = QPageLayout(
            QPageSize(QPageSize.PageSizeId.Letter),
            QPageLayout.Orientation.Portrait,
            QMarginsF(72, 72, 72, 72)  # 1 inch margins
        )
        printer.setPageLayout(page_layout)
        
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QPrintDialog.DialogCode.Accepted:
            self._editor.document().print(printer)
    
    # =========================================================================
    # Formatting Methods
    # =========================================================================
    
    def set_font_family(self, family: str) -> None:
        """Set font family for selection or future text."""
        fmt = QTextCharFormat()
        fmt.setFontFamily(family)
        self._merge_format_on_selection(fmt)
    
    def set_font_size(self, size: int) -> None:
        """Set font size for selection or future text."""
        fmt = QTextCharFormat()
        fmt.setFontPointSize(size)
        self._merge_format_on_selection(fmt)
    
    def toggle_bold(self) -> None:
        """Toggle bold formatting."""
        fmt = QTextCharFormat()
        cursor = self._editor.textCursor()
        current_weight = cursor.charFormat().fontWeight()
        new_weight = QFont.Weight.Normal if current_weight == QFont.Weight.Bold else QFont.Weight.Bold
        fmt.setFontWeight(new_weight)
        self._merge_format_on_selection(fmt)
    
    def toggle_italic(self) -> None:
        """Toggle italic formatting."""
        fmt = QTextCharFormat()
        cursor = self._editor.textCursor()
        fmt.setFontItalic(not cursor.charFormat().fontItalic())
        self._merge_format_on_selection(fmt)
    
    def toggle_underline(self) -> None:
        """Toggle underline formatting."""
        fmt = QTextCharFormat()
        cursor = self._editor.textCursor()
        fmt.setFontUnderline(not cursor.charFormat().fontUnderline())
        self._merge_format_on_selection(fmt)
    
    def toggle_strikethrough(self) -> None:
        """Toggle strikethrough formatting."""
        fmt = QTextCharFormat()
        cursor = self._editor.textCursor()
        fmt.setFontStrikeOut(not cursor.charFormat().fontStrikeOut())
        self._merge_format_on_selection(fmt)
    
    def set_text_color(self, color: QColor) -> None:
        """Set text color."""
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        self._merge_format_on_selection(fmt)
    
    def set_highlight_color(self, color: QColor) -> None:
        """Set highlight/background color."""
        fmt = QTextCharFormat()
        fmt.setBackground(color)
        self._merge_format_on_selection(fmt)
    
    def set_alignment(self, alignment: Qt.AlignmentFlag) -> None:
        """Set paragraph alignment."""
        self._editor.setAlignment(alignment)
    
    def toggle_bullet_list(self) -> None:
        """Toggle bullet list."""
        cursor = self._editor.textCursor()
        current_list = cursor.currentList()
        
        if current_list and current_list.format().style() == QTextListFormat.Style.ListDisc:
            # Remove list
            block_fmt = QTextBlockFormat()
            block_fmt.setIndent(0)
            cursor.setBlockFormat(block_fmt)
        else:
            # Create bullet list
            list_fmt = QTextListFormat()
            list_fmt.setStyle(QTextListFormat.Style.ListDisc)
            cursor.createList(list_fmt)
    
    def toggle_numbered_list(self) -> None:
        """Toggle numbered list."""
        cursor = self._editor.textCursor()
        current_list = cursor.currentList()
        
        if current_list and current_list.format().style() == QTextListFormat.Style.ListDecimal:
            # Remove list
            block_fmt = QTextBlockFormat()
            block_fmt.setIndent(0)
            cursor.setBlockFormat(block_fmt)
        else:
            # Create numbered list
            list_fmt = QTextListFormat()
            list_fmt.setStyle(QTextListFormat.Style.ListDecimal)
            cursor.createList(list_fmt)
    
    def increase_indent(self) -> None:
        """Increase paragraph indent."""
        cursor = self._editor.textCursor()
        block_fmt = cursor.blockFormat()
        block_fmt.setIndent(block_fmt.indent() + 1)
        cursor.setBlockFormat(block_fmt)
    
    def decrease_indent(self) -> None:
        """Decrease paragraph indent."""
        cursor = self._editor.textCursor()
        block_fmt = cursor.blockFormat()
        if block_fmt.indent() > 0:
            block_fmt.setIndent(block_fmt.indent() - 1)
            cursor.setBlockFormat(block_fmt)
    
    def _merge_format_on_selection(self, fmt: QTextCharFormat) -> None:
        """Apply format to selection or set for future typing."""
        cursor = self._editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        cursor.mergeCharFormat(fmt)
        self._editor.mergeCurrentCharFormat(fmt)
    
    # =========================================================================
    # Insert Methods
    # =========================================================================
    
    def insert_image(self) -> None:
        """Insert an image at cursor position."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Insert Image",
            "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp);;All Files (*)"
        )
        
        if not file_path:
            return
        
        image = QImage(file_path)
        if image.isNull():
            QMessageBox.warning(self, "Error", "Failed to load image.")
            return
        
        # Scale if too large
        max_width = 600
        if image.width() > max_width:
            image = image.scaledToWidth(max_width, Qt.TransformationMode.SmoothTransformation)
        
        # Insert into document
        cursor = self._editor.textCursor()
        document = self._editor.document()
        
        # Create unique name for image resource
        image_name = f"image_{id(image)}"
        document.addResource(
            QTextDocument.ResourceType.ImageResource,
            image_name,
            image
        )
        
        image_format = QTextImageFormat()
        image_format.setName(image_name)
        image_format.setWidth(image.width())
        image_format.setHeight(image.height())
        
        cursor.insertImage(image_format)
    
    def insert_table(self) -> None:
        """Insert a table at cursor position."""
        rows, ok1 = QInputDialog.getInt(
            self, "Insert Table", "Number of rows:", 3, 1, 100
        )
        if not ok1:
            return
        
        cols, ok2 = QInputDialog.getInt(
            self, "Insert Table", "Number of columns:", 3, 1, 20
        )
        if not ok2:
            return
        
        cursor = self._editor.textCursor()
        
        table_format = QTextTableFormat()
        table_format.setBorder(1)
        table_format.setBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
        table_format.setCellPadding(5)
        table_format.setCellSpacing(0)
        
        cursor.insertTable(rows, cols, table_format)
    
    def insert_horizontal_rule(self) -> None:
        """Insert a horizontal rule."""
        cursor = self._editor.textCursor()
        cursor.insertHtml("<hr>")
    
    def insert_latex_equation(self, latex: str) -> None:
        """Insert a LaTeX equation as rendered image."""
        try:
            # Try to render LaTeX using matplotlib
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            from io import BytesIO
            
            fig, ax = plt.subplots(figsize=(0.01, 0.01))
            ax.axis('off')
            
            # Render the LaTeX
            text = ax.text(0.5, 0.5, f"${latex}$", 
                          transform=ax.transAxes,
                          fontsize=14,
                          ha='center', va='center')
            
            # Get the bounding box
            fig.canvas.draw()
            bbox = text.get_window_extent(fig.canvas.get_renderer())
            
            # Resize figure to fit text
            fig.set_size_inches(bbox.width / fig.dpi + 0.2, bbox.height / fig.dpi + 0.2)
            
            # Save to buffer
            buffer = BytesIO()
            fig.savefig(buffer, format='png', dpi=150, 
                       bbox_inches='tight', pad_inches=0.1,
                       transparent=True)
            plt.close(fig)
            
            buffer.seek(0)
            image = QImage()
            image.loadFromData(buffer.getvalue())
            
            if not image.isNull():
                cursor = self._editor.textCursor()
                document = self._editor.document()
                
                image_name = f"latex_{id(image)}"
                document.addResource(
                    QTextDocument.ResourceType.ImageResource,
                    image_name,
                    image
                )
                
                image_format = QTextImageFormat()
                image_format.setName(image_name)
                cursor.insertImage(image_format)
            
        except ImportError:
            # Matplotlib not available, insert as text placeholder
            cursor = self._editor.textCursor()
            cursor.insertHtml(f'<span style="font-family: monospace; background-color: #f0f0f0;">[LaTeX: {latex}]</span>')
        except Exception as e:
            QMessageBox.warning(
                self,
                "LaTeX Error",
                f"Failed to render LaTeX:\n{e}\n\nEquation will be inserted as text."
            )
            cursor = self._editor.textCursor()
            cursor.insertHtml(f'<span style="font-family: monospace; background-color: #f0f0f0;">[LaTeX: {latex}]</span>')
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def get_current_format(self) -> Dict[str, Any]:
        """Get current text format at cursor for toolbar state updates."""
        cursor = self._editor.textCursor()
        char_fmt = cursor.charFormat()
        block_fmt = cursor.blockFormat()
        
        return {
            "font_family": char_fmt.fontFamily(),
            "font_size": int(char_fmt.fontPointSize()) if char_fmt.fontPointSize() > 0 else 11,
            "bold": char_fmt.fontWeight() == QFont.Weight.Bold,
            "italic": char_fmt.fontItalic(),
            "underline": char_fmt.fontUnderline(),
            "strikethrough": char_fmt.fontStrikeOut(),
            "text_color": char_fmt.foreground().color(),
            "highlight_color": char_fmt.background().color(),
            "alignment": self._editor.alignment(),
        }
    
    def has_changes(self) -> bool:
        """Check if document has unsaved changes."""
        return self._has_changes
    
    def get_title(self) -> str:
        """Get document title."""
        return self._document_title
    
    def set_title(self, title: str) -> None:
        """Set document title."""
        self._document_title = title
        self.title_changed.emit(title)
    
    @property
    def file_path(self) -> Optional[Path]:
        """Get current file path."""
        return self._file_path
    
    def focus_editor(self) -> None:
        """Set focus to the editor."""
        self._editor.setFocus()
    
    def undo(self) -> None:
        """Undo last action."""
        self._editor.undo()
    
    def redo(self) -> None:
        """Redo last undone action."""
        self._editor.redo()
    
    def cut(self) -> None:
        """Cut selection."""
        self._editor.cut()
    
    def copy(self) -> None:
        """Copy selection."""
        self._editor.copy()
    
    def paste(self) -> None:
        """Paste from clipboard."""
        self._editor.paste()
    
    def select_all(self) -> None:
        """Select all content."""
        self._editor.selectAll()
    
    def find_text(self, text: str, case_sensitive: bool = False) -> bool:
        """Find text in document."""
        flags = QTextDocument.FindFlag(0)
        if case_sensitive:
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        return self._editor.find(text, flags)
    
    def replace_text(self, find: str, replace: str) -> bool:
        """Replace current selection if it matches find text."""
        cursor = self._editor.textCursor()
        if cursor.selectedText().lower() == find.lower():
            cursor.insertText(replace)
            return True
        return self.find_text(find)
    
    def replace_all(self, find: str, replace: str) -> int:
        """Replace all occurrences. Returns count."""
        cursor = self._editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self._editor.setTextCursor(cursor)
        
        count = 0
        while self._editor.find(find):
            cursor = self._editor.textCursor()
            cursor.insertText(replace)
            count += 1
        
        return count
