"""
Viewer Widget

The main PDF viewing widget with annotation support.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict, Any, List

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QScrollArea,
    QLabel,
    QApplication,
    QInputDialog,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QPoint, QPointF, QRect, QSize, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QImage,
    QPixmap,
    QPainter,
    QPen,
    QBrush,
    QColor,
    QCursor,
    QWheelEvent,
    QMouseEvent,
    QKeyEvent,
    QPaintEvent,
    QResizeEvent,
)

from core.pdf_engine import PDFEngine
from core.render_engine import RenderEngine
from models.annotation import AnnotationBase, AnnotationType


class ViewerWidget(QWidget):
    """
    PDF viewer widget with annotation support.
    
    Signals:
        page_changed: Emitted when page changes (current_page, total_pages)
        zoom_changed: Emitted when zoom level changes (zoom_level)
        annotation_added: Emitted when annotation is added
        annotation_removed: Emitted when annotation is removed
        selection_changed: Emitted when text/area selection changes
    """
    
    page_changed = pyqtSignal(int, int)
    zoom_changed = pyqtSignal(float)
    annotation_added = pyqtSignal(object)
    annotation_removed = pyqtSignal(object)
    selection_changed = pyqtSignal()
    
    # Zoom levels
    MIN_ZOOM = 0.1
    MAX_ZOOM = 5.0
    ZOOM_STEP = 0.1
    
    def __init__(
        self,
        file_path: Path,
        services: Dict[str, Any],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        
        self._file_path = file_path
        self._services = services
        
        # PDF engine and document
        self._pdf_engine = PDFEngine()
        self._render_engine = RenderEngine()
        self._document = None
        
        # View state
        self._current_page = 0
        self._page_count = 0
        self._zoom_level = 1.0
        self._rotation = 0
        
        # Page cache
        self._page_pixmaps: Dict[int, QPixmap] = {}
        self._page_zoom_levels: Dict[int, float] = {}
        self._page_sizes: Dict[int, QSize] = {}
        
        # Scroll position
        self._scroll_offset = QPoint(0, 0)
        self._is_dragging = False
        self._drag_start_pos = QPoint()
        self._drag_start_scroll = QPoint()
        
        # Current tool
        self._current_tool = "draw"
        
        # Drawing settings
        self._stroke_color = QColor(255, 0, 0)
        self._fill_color = QColor(255, 255, 0, 128)
        self._stroke_width = 2
        
        # Lens tool settings
        self._lens_zoom = 3.0
        self._lens_mouse_pos = QPoint(0, 0)
        self._lens_active = False
        self._lens_view_pos = QPointF(0.5, 0.5)  # Normalized position (0-1) on page
        self._lens_dragging = False
        
        # Annotations
        self._annotations: List[AnnotationBase] = []
        self._current_annotation: Optional[AnnotationBase] = None
        self._selected_annotation: Optional[AnnotationBase] = None
        
        # Drawing state
        self._is_drawing = False
        self._drawings_visible = True  # Toggle to show/hide drawings
        self._draw_points: List[QPoint] = []
        self._draw_start_pos: Optional[QPoint] = None
        self._draw_end_pos: Optional[QPoint] = None
        
        # Page drawings - Dict[page_num, List[drawing_data]]
        self._page_drawings: Dict[int, List[dict]] = {}
        
        # Undo/redo stacks
        self._undo_stack: List[dict] = []
        self._redo_stack: List[dict] = []
        
        # Changes tracking
        self._has_changes = False
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the viewer UI."""
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        
        # Set background color
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(64, 64, 64))
        self.setPalette(palette)
    
    @property
    def file_path(self) -> Path:
        """Get the file path of the document."""
        return self._file_path
    
    @property
    def current_page(self) -> int:
        """Get the current page number (0-based)."""
        return self._current_page
    
    @property
    def page_count(self) -> int:
        """Get the total number of pages."""
        return self._page_count
    
    @property
    def zoom_level(self) -> float:
        """Get the current zoom level."""
        return self._zoom_level
    
    def open_document(self) -> bool:
        """
        Open the PDF document.
        
        Returns:
            True if document was opened successfully.
        """
        result = self._pdf_engine.load_document(self._file_path)
        if result.is_failure():
            return False
        
        self._document = result.unwrap()
        
        # Get page count directly from document
        self._page_count = self._document.page_count
        
        # Load page sizes
        for i in range(self._page_count):
            page_info_result = self._document.get_page_info(i)
            if page_info_result.is_success():
                page_info = page_info_result.unwrap()
                self._page_sizes[i] = QSize(int(page_info.width), int(page_info.height))
        
        # Render first page
        self._render_current_page()
        
        # Emit signals
        self.page_changed.emit(self._current_page, self._page_count)
        
        return True
    
    def close_document(self) -> None:
        """Close the current document."""
        if self._document:
            self._document.close()
            self._document = None
        
        self._page_pixmaps.clear()
        self._page_sizes.clear()
        self._annotations.clear()
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._has_changes = False
    
    def _render_current_page(self) -> None:
        """Render the current page."""
        if not self._document:
            return
        
        # Check cache first
        if self._current_page in self._page_pixmaps:
            cache_zoom = self._page_zoom_levels.get(self._current_page, 0)
            if cache_zoom == self._zoom_level:
                self.update()
                return
        
        # Render page
        result = self._pdf_engine.render_page_to_pixmap(
            self._document,
            self._current_page,
            scale=self._zoom_level,
        )
        
        if result.is_failure():
            return
        
        pixmap = result.unwrap()
        
        # Convert to QImage
        if pixmap.alpha:
            qimage = QImage(
                pixmap.samples,
                pixmap.width,
                pixmap.height,
                pixmap.stride,
                QImage.Format.Format_RGBA8888,
            )
        else:
            qimage = QImage(
                pixmap.samples,
                pixmap.width,
                pixmap.height,
                pixmap.stride,
                QImage.Format.Format_RGB888,
            )
        
        # Store in cache
        self._page_pixmaps[self._current_page] = QPixmap.fromImage(qimage)
        self._page_zoom_levels[self._current_page] = self._zoom_level
        
        self.update()
    
    # Navigation methods
    def go_to_page(self, page: int) -> None:
        """Go to a specific page."""
        if not self._document:
            return
        
        page = max(0, min(page, self._page_count - 1))
        if page != self._current_page:
            self._current_page = page
            self._scroll_offset.setX(0)
            self._scroll_offset.setY(0)
            self._render_current_page()
            self.page_changed.emit(self._current_page, self._page_count)
    
    def go_to_first_page(self) -> None:
        """Go to the first page."""
        self.go_to_page(0)
    
    def go_to_last_page(self) -> None:
        """Go to the last page."""
        self.go_to_page(self._page_count - 1)
    
    def go_to_previous_page(self) -> None:
        """Go to the previous page."""
        self.go_to_page(self._current_page - 1)
    
    def go_to_next_page(self) -> None:
        """Go to the next page."""
        self.go_to_page(self._current_page + 1)
    
    def show_go_to_page_dialog(self) -> None:
        """Show dialog to go to a specific page."""
        page, ok = QInputDialog.getInt(
            self,
            "Go to Page",
            f"Enter page number (1-{self._page_count}):",
            self._current_page + 1,
            1,
            self._page_count,
        )
        
        if ok:
            self.go_to_page(page - 1)
    
    # View mode methods
    def set_view_mode(self, mode: str) -> None:
        """Set view mode: 'single' or 'continuous'."""
        # Currently only single page mode is implemented
        self._scroll_offset = QPoint(0, 0)
        self.update()
    
    # Zoom methods
    def zoom_in(self) -> None:
        """Zoom in."""
        self.set_zoom(self._zoom_level + self.ZOOM_STEP)
    
    def zoom_out(self) -> None:
        """Zoom out."""
        self.set_zoom(self._zoom_level - self.ZOOM_STEP)
    
    def zoom_reset(self) -> None:
        """Reset zoom to 100%."""
        self.set_zoom(1.0)
    
    def set_zoom(self, zoom: float) -> None:
        """Set the zoom level."""
        zoom = max(self.MIN_ZOOM, min(zoom, self.MAX_ZOOM))
        if zoom != self._zoom_level:
            self._zoom_level = zoom
            self._render_current_page()
            self.zoom_changed.emit(self._zoom_level)
    
    def fit_width(self) -> None:
        """Fit page width to view."""
        if self._current_page in self._page_sizes:
            page_size = self._page_sizes[self._current_page]
            zoom = (self.width() - 40) / page_size.width()
            self.set_zoom(zoom)
    
    def fit_page(self) -> None:
        """Fit entire page to view."""
        if self._current_page in self._page_sizes:
            page_size = self._page_sizes[self._current_page]
            zoom_w = (self.width() - 40) / page_size.width()
            zoom_h = (self.height() - 40) / page_size.height()
            self.set_zoom(min(zoom_w, zoom_h))
    
    # Rotation methods
    def rotate_left(self) -> None:
        """Rotate page left (counter-clockwise)."""
        self._rotation = (self._rotation - 90) % 360
        self._render_current_page()
    
    def rotate_right(self) -> None:
        """Rotate page right (clockwise)."""
        self._rotation = (self._rotation + 90) % 360
        self._render_current_page()
    
    # Tool methods
    def set_current_tool(self, tool: str) -> None:
        """Set the current tool."""
        self._current_tool = tool
        self._lens_active = (tool == "lens")
        
        # Update cursor based on tool
        if tool == "draw":
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif tool in ("rectangle", "ellipse", "line", "arrow"):
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif tool == "eraser":
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif tool == "lens":
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.setMouseTracking(True)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.setMouseTracking(False)
    
    def set_stroke_color(self, color: QColor) -> None:
        """Set the stroke color for drawing."""
        self._stroke_color = color
    
    def set_fill_color(self, color: QColor) -> None:
        """Set the fill color for drawing."""
        self._fill_color = color
    
    def set_stroke_width(self, width: int) -> None:
        """Set the stroke width for drawing."""
        self._stroke_width = width
    
    def set_lens_zoom(self, zoom: float) -> None:
        """Set the lens zoom level."""
        self._lens_zoom = zoom
        if self._lens_active:
            self.update()
    
    def clear_all_drawings(self) -> None:
        """Clear all drawings on the current page."""
        if self._current_page in self._page_drawings:
            self._page_drawings[self._current_page].clear()
            self._has_changes = True
            self.update()
    
    def set_drawings_visible(self, visible: bool) -> None:
        """Show or hide all drawings."""
        self._drawings_visible = visible
        self.update()
    
    def are_drawings_visible(self) -> bool:
        """Check if drawings are visible."""
        return self._drawings_visible
    
    def toggle_drawings_visibility(self) -> bool:
        """Toggle drawings visibility. Returns new state."""
        self._drawings_visible = not self._drawings_visible
        self.update()
        return self._drawings_visible
    
    # Annotation methods
    def save_annotations(self) -> bool:
        """Save annotations to database."""
        # TODO: Implement annotation persistence
        self._has_changes = False
        return True
    
    def save_as(self, file_path: str) -> bool:
        """Save document with annotations to a new file."""
        # TODO: Implement save as
        return False
    
    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes."""
        return self._has_changes
    
    # Undo/redo methods
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return len(self._undo_stack) > 0
    
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return len(self._redo_stack) > 0
    
    def undo(self) -> None:
        """Undo the last action."""
        if self._undo_stack:
            action = self._undo_stack.pop()
            self._redo_stack.append(action)
            self._apply_undo_action(action)
            self.update()
    
    def redo(self) -> None:
        """Redo the last undone action."""
        if self._redo_stack:
            action = self._redo_stack.pop()
            self._undo_stack.append(action)
            self._apply_redo_action(action)
            self.update()
    
    def _apply_undo_action(self, action: dict) -> None:
        """Apply an undo action."""
        # TODO: Implement undo logic
        pass
    
    def _apply_redo_action(self, action: dict) -> None:
        """Apply a redo action."""
        # TODO: Implement redo logic
        pass
    
    # Selection methods
    def copy_selection(self) -> None:
        """Copy selected text to clipboard."""
        # TODO: Implement text selection copy
        pass
    
    def select_all(self) -> None:
        """Select all text on current page."""
        # TODO: Implement select all
        pass
    
    # Search methods
    def show_find_dialog(self) -> None:
        """Show the find dialog."""
        # TODO: Implement find dialog
        pass
    
    def find_next(self) -> None:
        """Find next occurrence."""
        # TODO: Implement find next
        pass
    
    # Export/print methods
    def show_export_dialog(self) -> None:
        """Show export dialog."""
        # TODO: Implement export dialog
        pass
    
    def print_document(self) -> None:
        """Print the document."""
        # TODO: Implement printing
        pass
    
    # Event handlers
    def paintEvent(self, event: QPaintEvent) -> None:
        """Handle paint event."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background
        painter.fillRect(self.rect(), QColor(64, 64, 64))
        
        # If lens tool is active, render split view
        if self._lens_active and self._current_page in self._page_pixmaps:
            self._draw_lens_view(painter)
            painter.end()
            return
        
        # Draw page
        if self._current_page in self._page_pixmaps:
            pixmap = self._page_pixmaps[self._current_page]
            
            # Calculate centered position with scroll offset
            # X is always centered (no horizontal scroll for now)
            x = (self.width() - pixmap.width()) // 2
            
            # Y position: center if page fits, otherwise apply scroll
            if pixmap.height() <= self.height() - 20:
                # Page fits vertically - center it
                y = (self.height() - pixmap.height()) // 2
            else:
                # Page doesn't fit - start from top with scroll offset
                y = 20 - self._scroll_offset.y()
            
            # Draw shadow
            shadow_rect = QRect(x + 4, y + 4, pixmap.width(), pixmap.height())
            painter.fillRect(shadow_rect, QColor(0, 0, 0, 60))
            
            # Draw white page background
            page_rect = QRect(x, y, pixmap.width(), pixmap.height())
            painter.fillRect(page_rect, QColor(255, 255, 255))
            
            # Draw page content
            painter.drawPixmap(x, y, pixmap)
            
            # Draw saved drawings for this page (if visible)
            if self._drawings_visible:
                self._draw_page_drawings(painter, x, y)
            
            # Draw annotations
            self._draw_annotations(painter, x, y)
            
            # Draw current drawing in progress
            if self._is_drawing:
                self._draw_current_drawing(painter, x, y)
        else:
            # No page loaded - show loading message
            painter.setPen(QColor(200, 200, 200))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Loading...")
        
        painter.end()
    
    def _draw_lens_view(self, painter: QPainter) -> None:
        """Draw the lens split-view with full page on left and zoomed section in center."""
        pixmap = self._page_pixmaps[self._current_page]
        widget_width = self.width()
        widget_height = self.height()
        
        # Calculate layout: left panel (20% width) for thumbnail, center for zoomed view
        left_panel_width = int(widget_width * 0.20)
        center_panel_x = left_panel_width + 10  # Start of center panel with margin
        center_panel_width = widget_width - center_panel_x - 10
        
        # === Left Panel: Full page thumbnail ===
        # Scale pixmap to fit in left panel
        margin = 10
        available_width = left_panel_width - margin * 2
        available_height = widget_height - margin * 2
        
        scale_w = available_width / pixmap.width()
        scale_h = available_height / pixmap.height()
        thumb_scale = min(scale_w, scale_h)
        
        thumb_width = int(pixmap.width() * thumb_scale)
        thumb_height = int(pixmap.height() * thumb_scale)
        thumb_x = margin + (available_width - thumb_width) // 2
        thumb_y = margin + (available_height - thumb_height) // 2
        
        # Draw left panel background
        painter.fillRect(0, 0, left_panel_width, widget_height, QColor(50, 50, 50))
        
        # Draw scaled thumbnail
        thumb_pixmap = pixmap.scaled(thumb_width, thumb_height, 
                                      Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
        painter.drawPixmap(thumb_x, thumb_y, thumb_pixmap)
        
        # Draw border around thumbnail
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawRect(thumb_x - 1, thumb_y - 1, thumb_width + 2, thumb_height + 2)
        
        # === Calculate view position on original pixmap using normalized position ===
        mouse_on_pixmap_x = self._lens_view_pos.x() * pixmap.width()
        mouse_on_pixmap_y = self._lens_view_pos.y() * pixmap.height()
        
        # === Calculate zoomed view dimensions ===
        # Width always fills the center panel, height shrinks with higher zoom
        zoomed_display_width = center_panel_width - 20  # Leave some margin
        
        # Calculate how much of the original page width we're viewing
        original_view_width = zoomed_display_width / self._lens_zoom
        # Keep aspect ratio - height is proportional
        original_view_height = original_view_width * (widget_height - 60) / zoomed_display_width
        # But limit by zoom level - higher zoom = less height
        original_view_height = min(original_view_height, pixmap.height() / self._lens_zoom)
        
        # Position of view rect on original (centered on view position)
        view_left = mouse_on_pixmap_x - original_view_width / 2
        view_top = mouse_on_pixmap_y - original_view_height / 2
        
        # Scale to thumbnail coordinates
        thumb_view_x = thumb_x + view_left * thumb_scale
        thumb_view_y = thumb_y + view_top * thumb_scale
        thumb_view_w = original_view_width * thumb_scale
        thumb_view_h = original_view_height * thumb_scale
        
        # Draw view rectangle indicator on thumbnail
        painter.setPen(QPen(QColor(255, 100, 100), 2))
        painter.setBrush(QBrush(QColor(255, 100, 100, 50)))
        painter.drawRect(int(thumb_view_x), int(thumb_view_y), int(thumb_view_w), int(thumb_view_h))
        
        # === Center Panel: Zoomed view ===
        # Draw center panel background
        painter.fillRect(center_panel_x, 0, center_panel_width, widget_height, QColor(64, 64, 64))
        
        # Calculate the source rectangle to zoom
        src_x = int(mouse_on_pixmap_x - original_view_width / 2)
        src_y = int(mouse_on_pixmap_y - original_view_height / 2)
        src_width = int(original_view_width)
        src_height = int(original_view_height)
        
        # Clamp source rect to pixmap bounds
        if src_x < 0:
            src_x = 0
        if src_y < 0:
            src_y = 0
        if src_x + src_width > pixmap.width():
            src_width = pixmap.width() - src_x
        if src_y + src_height > pixmap.height():
            src_height = pixmap.height() - src_y
        
        if src_width > 0 and src_height > 0:
            # Extract and scale the portion - width fills panel, height based on zoom
            zoomed_portion = pixmap.copy(src_x, src_y, src_width, src_height)
            scaled_width = int(src_width * self._lens_zoom)
            scaled_height = int(src_height * self._lens_zoom)
            
            scaled_portion = zoomed_portion.scaled(
                scaled_width,
                scaled_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # Center the zoomed portion in the center panel
            zoom_x = center_panel_x + (center_panel_width - scaled_portion.width()) // 2
            zoom_y = (widget_height - scaled_portion.height()) // 2
            
            # Draw white background for zoomed area
            painter.fillRect(zoom_x - 2, zoom_y - 2, 
                           scaled_portion.width() + 4, scaled_portion.height() + 4, 
                           QColor(255, 255, 255))
            
            # Draw zoomed content
            painter.drawPixmap(zoom_x, zoom_y, scaled_portion)
            
            # Draw border
            painter.setPen(QPen(QColor(100, 100, 100), 2))
            painter.drawRect(zoom_x - 2, zoom_y - 2, 
                           scaled_portion.width() + 4, scaled_portion.height() + 4)
        
        # Draw zoom level indicator
        painter.setPen(QColor(200, 200, 200))
        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(center_panel_x + 10, 30, f"Zoom: {self._lens_zoom:.0f}x")
        
        # Draw instructions
        font.setPointSize(10)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(thumb_x, thumb_y + thumb_height + 20, "Click & drag to move")
        
        # Draw divider line between panels
        painter.setPen(QPen(QColor(80, 80, 80), 2))
        painter.drawLine(left_panel_width, 0, left_panel_width, widget_height)

    def _draw_page_drawings(self, painter: QPainter, offset_x: int, offset_y: int) -> None:
        """Draw saved drawings on the current page."""
        if self._current_page not in self._page_drawings:
            return
        
        for drawing in self._page_drawings[self._current_page]:
            self._render_drawing(painter, drawing, offset_x, offset_y)
    
    def _render_drawing(self, painter: QPainter, drawing: dict, offset_x: int, offset_y: int) -> None:
        """Render a single drawing."""
        tool = drawing.get("tool")
        color = drawing.get("color", QColor(255, 0, 0))
        fill_color = drawing.get("fill_color", QColor(255, 255, 0, 128))
        width = drawing.get("width", 2)
        
        pen = QPen(color)
        pen.setWidth(width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        
        if tool == "draw":
            # Freehand drawing - list of points
            points = drawing.get("points", [])
            if len(points) >= 2:
                for i in range(1, len(points)):
                    p1 = points[i - 1]
                    p2 = points[i]
                    painter.drawLine(
                        p1.x() + offset_x, p1.y() + offset_y,
                        p2.x() + offset_x, p2.y() + offset_y
                    )
        
        elif tool == "rectangle":
            rect = drawing.get("rect")
            if rect:
                adjusted_rect = QRect(
                    rect.x() + offset_x,
                    rect.y() + offset_y,
                    rect.width(),
                    rect.height()
                )
                painter.setBrush(QBrush(fill_color))
                painter.drawRect(adjusted_rect)
        
        elif tool == "ellipse":
            rect = drawing.get("rect")
            if rect:
                adjusted_rect = QRect(
                    rect.x() + offset_x,
                    rect.y() + offset_y,
                    rect.width(),
                    rect.height()
                )
                painter.setBrush(QBrush(fill_color))
                painter.drawEllipse(adjusted_rect)
        
        elif tool == "line":
            start = drawing.get("start")
            end = drawing.get("end")
            if start and end:
                painter.drawLine(
                    start.x() + offset_x, start.y() + offset_y,
                    end.x() + offset_x, end.y() + offset_y
                )
        
        elif tool == "arrow":
            start = drawing.get("start")
            end = drawing.get("end")
            if start and end:
                # Draw line
                painter.drawLine(
                    start.x() + offset_x, start.y() + offset_y,
                    end.x() + offset_x, end.y() + offset_y
                )
                # Draw arrowhead
                self._draw_arrowhead(painter, start, end, offset_x, offset_y)
    
    def _draw_arrowhead(self, painter: QPainter, start: QPoint, end: QPoint, offset_x: int, offset_y: int) -> None:
        """Draw arrowhead at the end point."""
        import math
        
        # Calculate angle
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        angle = math.atan2(dy, dx)
        
        # Arrow parameters
        arrow_length = 15
        arrow_angle = math.pi / 6  # 30 degrees
        
        # Calculate arrowhead points
        x1 = end.x() - arrow_length * math.cos(angle - arrow_angle)
        y1 = end.y() - arrow_length * math.sin(angle - arrow_angle)
        x2 = end.x() - arrow_length * math.cos(angle + arrow_angle)
        y2 = end.y() - arrow_length * math.sin(angle + arrow_angle)
        
        # Draw arrowhead lines
        painter.drawLine(
            end.x() + offset_x, end.y() + offset_y,
            int(x1) + offset_x, int(y1) + offset_y
        )
        painter.drawLine(
            end.x() + offset_x, end.y() + offset_y,
            int(x2) + offset_x, int(y2) + offset_y
        )
    
    def _draw_current_drawing(self, painter: QPainter, offset_x: int, offset_y: int) -> None:
        """Draw the current drawing in progress."""
        pen = QPen(self._stroke_color)
        pen.setWidth(self._stroke_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        
        if self._current_tool == "draw" and self._draw_points:
            # Freehand drawing - points are in page coordinates, add offset for display
            for i in range(1, len(self._draw_points)):
                p1 = self._draw_points[i - 1]
                p2 = self._draw_points[i]
                painter.drawLine(
                    p1.x() + offset_x, p1.y() + offset_y,
                    p2.x() + offset_x, p2.y() + offset_y
                )
        
        elif self._current_tool in ("rectangle", "ellipse", "line", "arrow"):
            if self._draw_start_pos and self._draw_end_pos:
                start = self._draw_start_pos
                end = self._draw_end_pos
                
                if self._current_tool == "rectangle":
                    rect = QRect(start, end).normalized()
                    painter.setBrush(QBrush(self._fill_color))
                    painter.drawRect(rect)
                
                elif self._current_tool == "ellipse":
                    rect = QRect(start, end).normalized()
                    painter.setBrush(QBrush(self._fill_color))
                    painter.drawEllipse(rect)
                
                elif self._current_tool == "line":
                    painter.drawLine(start, end)
                
                elif self._current_tool == "arrow":
                    painter.drawLine(start, end)
                    # Draw preview arrowhead
                    self._draw_arrowhead(painter, start, end, 0, 0)

    def _draw_annotations(self, painter: QPainter, offset_x: int, offset_y: int) -> None:
        """Draw annotations on the current page."""
        for annotation in self._annotations:
            if annotation.page_number == self._current_page:
                self._draw_annotation(painter, annotation, offset_x, offset_y)
    
    def _draw_annotation(
        self,
        painter: QPainter,
        annotation: AnnotationBase,
        offset_x: int,
        offset_y: int,
    ) -> None:
        """Draw a single annotation."""
        # TODO: Implement drawing for each annotation type
        pass
    
    def _draw_current_path(
        self,
        painter: QPainter,
        offset_x: int,
        offset_y: int,
    ) -> None:
        """Draw the current drawing path (legacy, kept for compatibility)."""
        if len(self._draw_points) < 2:
            return
        
        pen = QPen(self._stroke_color)
        pen.setWidth(self._stroke_width)
        painter.setPen(pen)
        
        for i in range(1, len(self._draw_points)):
            p1 = self._draw_points[i - 1]
            p2 = self._draw_points[i]
            painter.drawLine(p1, p2)
    
    def _get_page_offset(self) -> tuple:
        """Get the current page offset for coordinate conversion."""
        if self._current_page not in self._page_pixmaps:
            return 0, 0
        
        pixmap = self._page_pixmaps[self._current_page]
        x = (self.width() - pixmap.width()) // 2
        
        if pixmap.height() <= self.height() - 20:
            y = (self.height() - pixmap.height()) // 2
        else:
            y = 20 - self._scroll_offset.y()
        
        return x, y
    
    def _screen_to_page_coords(self, pos: QPoint) -> QPoint:
        """Convert screen coordinates to page coordinates."""
        offset_x, offset_y = self._get_page_offset()
        return QPoint(pos.x() - offset_x, pos.y() - offset_y)
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press event."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Handle lens tool - start dragging
            if self._lens_active:
                self._lens_dragging = True
                self._update_lens_position(event.pos())
                return
            
            if self._current_tool == "draw":
                self._is_drawing = True
                # Convert to page coordinates
                page_pos = self._screen_to_page_coords(event.pos())
                self._draw_points = [page_pos]
            
            elif self._current_tool in ("rectangle", "ellipse", "line", "arrow"):
                self._is_drawing = True
                self._draw_start_pos = event.pos()
                self._draw_end_pos = event.pos()
            
            elif self._current_tool == "eraser":
                # Try to erase drawing at click position
                self._erase_at_position(event.pos())
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move event."""
        # Update lens position if lens tool is active and dragging
        if self._lens_active:
            if self._lens_dragging or event.buttons() & Qt.MouseButton.LeftButton:
                self._update_lens_position(event.pos())
            self.update()
            return
        
        if self._is_drawing:
            if self._current_tool == "draw":
                # Add point in page coordinates
                page_pos = self._screen_to_page_coords(event.pos())
                self._draw_points.append(page_pos)
            elif self._current_tool in ("rectangle", "ellipse", "line", "arrow"):
                self._draw_end_pos = event.pos()
            self.update()
        elif self._current_tool == "eraser" and event.buttons() & Qt.MouseButton.LeftButton:
            # Continue erasing while dragging
            self._erase_at_position(event.pos())
    
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release event."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Handle lens tool - stop dragging
            if self._lens_active:
                self._lens_dragging = False
                return
            
            if self._is_drawing:
                self._is_drawing = False
                self._finalize_drawing()
    
    def _update_lens_position(self, mouse_pos: QPoint) -> None:
        """Update the lens view position based on mouse click/drag on the thumbnail."""
        if self._current_page not in self._page_pixmaps:
            return
        
        pixmap = self._page_pixmaps[self._current_page]
        widget_width = self.width()
        widget_height = self.height()
        
        # Calculate thumbnail bounds (same as in _draw_lens_view)
        left_panel_width = int(widget_width * 0.25)
        margin = 20
        available_width = left_panel_width - margin * 2
        available_height = widget_height - margin * 2
        
        scale_w = available_width / pixmap.width()
        scale_h = available_height / pixmap.height()
        thumb_scale = min(scale_w, scale_h)
        
        thumb_width = int(pixmap.width() * thumb_scale)
        thumb_height = int(pixmap.height() * thumb_scale)
        thumb_x = margin + (available_width - thumb_width) // 2
        thumb_y = margin + (available_height - thumb_height) // 2
        
        # Check if click is on thumbnail
        if (thumb_x <= mouse_pos.x() <= thumb_x + thumb_width and
            thumb_y <= mouse_pos.y() <= thumb_y + thumb_height):
            # Convert click to normalized position (0-1) on page
            norm_x = (mouse_pos.x() - thumb_x) / thumb_width
            norm_y = (mouse_pos.y() - thumb_y) / thumb_height
            self._lens_view_pos = QPointF(
                max(0.0, min(1.0, norm_x)),
                max(0.0, min(1.0, norm_y))
            )
    
    def _erase_at_position(self, pos: QPoint) -> None:
        """Erase drawing at the given position."""
        if self._current_page not in self._page_drawings:
            return
        
        page_pos = self._screen_to_page_coords(pos)
        eraser_radius = 10
        
        # Find and remove drawings near the click position
        drawings_to_remove = []
        for i, drawing in enumerate(self._page_drawings[self._current_page]):
            if self._is_point_near_drawing(page_pos, drawing, eraser_radius):
                drawings_to_remove.append(i)
        
        # Remove in reverse order to maintain indices
        for i in reversed(drawings_to_remove):
            self._page_drawings[self._current_page].pop(i)
            self._has_changes = True
        
        if drawings_to_remove:
            self.update()
    
    def _is_point_near_drawing(self, point: QPoint, drawing: dict, radius: int) -> bool:
        """Check if a point is near a drawing."""
        tool = drawing.get("tool")
        
        if tool == "draw":
            # Check if point is near any segment of the freehand drawing
            points = drawing.get("points", [])
            for p in points:
                if abs(p.x() - point.x()) < radius and abs(p.y() - point.y()) < radius:
                    return True
        
        elif tool in ("rectangle", "ellipse"):
            rect = drawing.get("rect")
            if rect:
                # Check if point is near the rectangle/ellipse border
                expanded_rect = rect.adjusted(-radius, -radius, radius, radius)
                return expanded_rect.contains(point)
        
        elif tool in ("line", "arrow"):
            start = drawing.get("start")
            end = drawing.get("end")
            if start and end:
                # Check distance from point to line segment
                return self._point_to_line_distance(point, start, end) < radius
        
        return False
    
    def _point_to_line_distance(self, point: QPoint, line_start: QPoint, line_end: QPoint) -> float:
        """Calculate distance from point to line segment."""
        import math
        
        dx = line_end.x() - line_start.x()
        dy = line_end.y() - line_start.y()
        
        if dx == 0 and dy == 0:
            return math.sqrt((point.x() - line_start.x())**2 + (point.y() - line_start.y())**2)
        
        t = max(0, min(1, ((point.x() - line_start.x()) * dx + (point.y() - line_start.y()) * dy) / (dx * dx + dy * dy)))
        
        proj_x = line_start.x() + t * dx
        proj_y = line_start.y() + t * dy
        
        return math.sqrt((point.x() - proj_x)**2 + (point.y() - proj_y)**2)
    
    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel event."""
        modifiers = event.modifiers()
        
        if modifiers == Qt.KeyboardModifier.ControlModifier:
            # Zoom with Ctrl+Wheel
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:
            # Page navigation with wheel (single page view)
            delta = event.angleDelta().y()
            
            if self._current_page in self._page_pixmaps:
                pixmap = self._page_pixmaps[self._current_page]
                
                # Calculate how much the page exceeds the view
                extra_height = pixmap.height() - self.height() + 40
                
                if extra_height > 0:
                    # Page is taller than view - allow scrolling within page
                    scroll_amount = 60
                    new_y = self._scroll_offset.y()
                    
                    if delta > 0:  # Scroll up
                        new_y -= scroll_amount
                    else:  # Scroll down
                        new_y += scroll_amount
                    
                    # Calculate scroll bounds (centered)
                    min_scroll = -extra_height // 2
                    max_scroll = extra_height // 2
                    
                    # Check if at boundary - change page
                    if new_y < min_scroll - 30:
                        if self._current_page > 0:
                            self.go_to_previous_page()
                            # Position at bottom of previous page
                            QTimer.singleShot(50, self._scroll_to_bottom)
                        return
                    elif new_y > max_scroll + 30:
                        if self._current_page < self._page_count - 1:
                            self.go_to_next_page()
                            # Position at top (already reset by go_to_page)
                        return
                    
                    # Clamp to bounds
                    new_y = max(min_scroll, min(new_y, max_scroll))
                    self._scroll_offset.setY(new_y)
                    self.update()
                else:
                    # Page fits in view - just change pages
                    if delta > 0:
                        if self._current_page > 0:
                            self.go_to_previous_page()
                    else:
                        if self._current_page < self._page_count - 1:
                            self.go_to_next_page()
    
    def _scroll_to_bottom(self) -> None:
        """Scroll to bottom of current page."""
        if self._current_page in self._page_pixmaps:
            pixmap = self._page_pixmaps[self._current_page]
            extra_height = pixmap.height() - self.height() + 40
            if extra_height > 0:
                self._scroll_offset.setY(extra_height // 2)
                self.update()
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press event."""
        key = event.key()
        
        if key == Qt.Key.Key_PageUp:
            self.go_to_previous_page()
        elif key == Qt.Key.Key_PageDown:
            self.go_to_next_page()
        elif key == Qt.Key.Key_Home:
            self.go_to_first_page()
        elif key == Qt.Key.Key_End:
            self.go_to_last_page()
        elif key == Qt.Key.Key_Plus:
            self.zoom_in()
        elif key == Qt.Key.Key_Minus:
            self.zoom_out()
        elif key == Qt.Key.Key_0:
            self.zoom_reset()
        elif key == Qt.Key.Key_Escape:
            self._cancel_current_action()
        else:
            super().keyPressEvent(event)
    
    def resizeEvent(self, event: QResizeEvent) -> None:
        """Handle resize event."""
        super().resizeEvent(event)
        self.update()
    
    def _check_annotation_selection(self, pos: QPoint) -> None:
        """Check if an annotation was clicked."""
        # TODO: Implement annotation hit testing
        pass
    
    def _finalize_drawing(self) -> None:
        """Finalize a drawing operation and save it."""
        # Initialize page drawings dict if needed
        if self._current_page not in self._page_drawings:
            self._page_drawings[self._current_page] = []
        
        offset_x, offset_y = self._get_page_offset()
        
        if self._current_tool == "draw":
            if len(self._draw_points) < 2:
                self._draw_points.clear()
                return
            
            # Save freehand drawing (already in page coordinates)
            drawing = {
                "tool": "draw",
                "points": list(self._draw_points),  # Copy the list
                "color": QColor(self._stroke_color),
                "width": self._stroke_width,
            }
            self._page_drawings[self._current_page].append(drawing)
            self._draw_points.clear()
        
        elif self._current_tool in ("rectangle", "ellipse"):
            if self._draw_start_pos and self._draw_end_pos:
                # Convert to page coordinates
                start_page = self._screen_to_page_coords(self._draw_start_pos)
                end_page = self._screen_to_page_coords(self._draw_end_pos)
                rect = QRect(start_page, end_page).normalized()
                
                if rect.width() > 5 and rect.height() > 5:
                    drawing = {
                        "tool": self._current_tool,
                        "rect": rect,
                        "color": QColor(self._stroke_color),
                        "fill_color": QColor(self._fill_color),
                        "width": self._stroke_width,
                    }
                    self._page_drawings[self._current_page].append(drawing)
        
        elif self._current_tool in ("line", "arrow"):
            if self._draw_start_pos and self._draw_end_pos:
                # Convert to page coordinates
                start_page = self._screen_to_page_coords(self._draw_start_pos)
                end_page = self._screen_to_page_coords(self._draw_end_pos)
                
                # Only save if line has some length
                import math
                length = math.sqrt((end_page.x() - start_page.x())**2 + (end_page.y() - start_page.y())**2)
                if length > 5:
                    drawing = {
                        "tool": self._current_tool,
                        "start": start_page,
                        "end": end_page,
                        "color": QColor(self._stroke_color),
                        "width": self._stroke_width,
                    }
                    self._page_drawings[self._current_page].append(drawing)
        
        # Reset drawing state
        self._draw_start_pos = None
        self._draw_end_pos = None
        self._has_changes = True
        self.update()
    
    def _cancel_current_action(self) -> None:
        """Cancel the current action."""
        self._is_drawing = False
        self._draw_points.clear()
        self._draw_start_pos = None
        self._draw_end_pos = None
        self._selected_annotation = None
        self.update()
