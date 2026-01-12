"""
Export Service

Handles PDF export operations including:
- Export with annotations embedded
- Export with annotations flattened
- Export selected pages
- Export to various formats (PDF, image)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Callable
from enum import Enum, auto
import threading
import io
import time

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QImage, QPainter

from core.error_types import (
    Result,
    Success,
    Failure,
    PDFError,
    FileSystemError,
)
from core.pdf_engine import PDFEngine
from models.annotation import AnnotationBase


class ExportFormat(Enum):
    """Supported export formats."""
    PDF = auto()
    PDF_FLATTENED = auto()
    PNG = auto()
    JPEG = auto()
    TIFF = auto()


class AnnotationExportMode(Enum):
    """How to handle annotations during export."""
    EMBED = auto()      # Embed as PDF annotations (editable)
    FLATTEN = auto()    # Render into page content (permanent)
    EXCLUDE = auto()    # Don't include annotations


@dataclass
class ExportOptions:
    """Options for export operations."""
    
    format: ExportFormat = ExportFormat.PDF
    annotation_mode: AnnotationExportMode = AnnotationExportMode.EMBED
    
    # Page selection
    pages: Optional[List[int]] = None  # None = all pages
    page_range: Optional[tuple[int, int]] = None  # Start and end page (inclusive)
    
    # Image export options
    dpi: int = 150
    image_quality: int = 90  # For JPEG
    
    # PDF options
    compress: bool = True
    linearize: bool = False  # Web-optimized
    
    # Metadata
    preserve_metadata: bool = True
    custom_metadata: Optional[dict] = None


@dataclass
class ExportProgress:
    """Progress information for export operations."""
    
    total_pages: int = 0
    processed_pages: int = 0
    current_stage: str = ""
    is_cancelled: bool = False
    error_message: Optional[str] = None
    
    @property
    def progress_percent(self) -> float:
        if self.total_pages == 0:
            return 0.0
        return (self.processed_pages / self.total_pages) * 100


@dataclass
class ExportResult:
    """Result of an export operation."""
    
    success: bool
    output_path: Optional[Path] = None
    output_paths: List[Path] = field(default_factory=list)  # For multi-file exports
    pages_exported: int = 0
    file_size_bytes: int = 0
    processing_time_ms: float = 0.0
    error_message: Optional[str] = None


class ExportService(QObject):
    """
    Service for exporting documents with annotations.
    
    Signals:
        export_started: Emitted when export begins
        export_progress: Emitted with progress updates (ExportProgress)
        export_completed: Emitted when export finishes (ExportResult)
    """
    
    export_started = pyqtSignal()
    export_progress = pyqtSignal(object)  # ExportProgress
    export_completed = pyqtSignal(object)  # ExportResult
    
    def __init__(self):
        super().__init__()
        
        self._pdf_engine = PDFEngine()
        self._cancel_requested = False
        self._lock = threading.Lock()
    
    def export_document(
        self,
        source_path: Path,
        output_path: Path,
        annotations: Optional[List[AnnotationBase]] = None,
        options: Optional[ExportOptions] = None,
        progress_callback: Optional[Callable[[ExportProgress], None]] = None,
    ) -> Result[ExportResult]:
        """
        Export a document with optional annotations.
        
        Args:
            source_path: Path to the source PDF.
            output_path: Path for the output file.
            annotations: List of annotations to include.
            options: Export options.
            progress_callback: Optional progress callback.
        
        Returns:
            Result containing ExportResult with details.
        """
        options = options or ExportOptions()
        start_time = time.time()
        
        self._cancel_requested = False
        self.export_started.emit()
        
        progress = ExportProgress(current_stage="Opening document")
        
        if progress_callback:
            progress_callback(progress)
        self.export_progress.emit(progress)
        
        # Open source document
        doc_result = self._pdf_engine.load_document(source_path)
        if doc_result.is_failure:
            return Failure(PDFError(
                message=f"Failed to open document: {doc_result.error}",
            ))
        
        pdf_doc = doc_result.value
        
        try:
            page_count_result = pdf_doc.get_page_count()
            if page_count_result.is_failure:
                return Failure(PDFError(message="Failed to get page count"))
            
            total_pages = page_count_result.value
            
            # Determine pages to export
            pages_to_export = self._get_pages_to_export(options, total_pages)
            progress.total_pages = len(pages_to_export)
            
            # Route to appropriate export method
            if options.format == ExportFormat.PDF:
                result = self._export_pdf(
                    pdf_doc,
                    output_path,
                    pages_to_export,
                    annotations,
                    options,
                    progress,
                    progress_callback,
                )
            elif options.format == ExportFormat.PDF_FLATTENED:
                options.annotation_mode = AnnotationExportMode.FLATTEN
                result = self._export_pdf(
                    pdf_doc,
                    output_path,
                    pages_to_export,
                    annotations,
                    options,
                    progress,
                    progress_callback,
                )
            elif options.format in (ExportFormat.PNG, ExportFormat.JPEG, ExportFormat.TIFF):
                result = self._export_images(
                    pdf_doc,
                    output_path,
                    pages_to_export,
                    annotations,
                    options,
                    progress,
                    progress_callback,
                )
            else:
                return Failure(PDFError(message=f"Unsupported format: {options.format}"))
            
            if result.is_failure:
                return result
            
            export_result = result.value
            export_result.processing_time_ms = (time.time() - start_time) * 1000
            
            self.export_completed.emit(export_result)
            return Success(export_result)
            
        finally:
            pdf_doc.close()
    
    def export_page_as_image(
        self,
        source_path: Path,
        page_number: int,
        output_path: Path,
        format: ExportFormat = ExportFormat.PNG,
        dpi: int = 150,
        annotations: Optional[List[AnnotationBase]] = None,
    ) -> Result[ExportResult]:
        """
        Export a single page as an image.
        
        Args:
            source_path: Path to the source PDF.
            page_number: Page number to export (0-based).
            output_path: Path for the output image.
            format: Image format.
            dpi: Resolution in DPI.
            annotations: Annotations to render on the page.
        
        Returns:
            Result containing ExportResult.
        """
        options = ExportOptions(
            format=format,
            dpi=dpi,
            pages=[page_number],
            annotation_mode=AnnotationExportMode.FLATTEN if annotations else AnnotationExportMode.EXCLUDE,
        )
        
        return self.export_document(
            source_path,
            output_path,
            annotations,
            options,
        )
    
    def cancel_export(self) -> None:
        """Request cancellation of current export operation."""
        self._cancel_requested = True
    
    def _get_pages_to_export(
        self,
        options: ExportOptions,
        total_pages: int,
    ) -> List[int]:
        """Determine which pages to export based on options."""
        if options.pages is not None:
            # Specific pages
            return [p for p in options.pages if 0 <= p < total_pages]
        
        if options.page_range is not None:
            start, end = options.page_range
            start = max(0, start)
            end = min(total_pages - 1, end)
            return list(range(start, end + 1))
        
        # All pages
        return list(range(total_pages))
    
    def _export_pdf(
        self,
        pdf_doc,
        output_path: Path,
        pages: List[int],
        annotations: Optional[List[AnnotationBase]],
        options: ExportOptions,
        progress: ExportProgress,
        progress_callback: Optional[Callable],
    ) -> Result[ExportResult]:
        """Export to PDF format."""
        try:
            import fitz
            
            progress.current_stage = "Creating output document"
            if progress_callback:
                progress_callback(progress)
            self.export_progress.emit(progress)
            
            # Create new PDF document
            output_doc = fitz.open()
            
            # Copy pages
            source_doc = pdf_doc._doc  # Access internal PyMuPDF document
            
            for i, page_num in enumerate(pages):
                if self._cancel_requested:
                    progress.is_cancelled = True
                    output_doc.close()
                    return Success(ExportResult(
                        success=False,
                        error_message="Export cancelled",
                    ))
                
                progress.current_stage = f"Processing page {i + 1}/{len(pages)}"
                progress.processed_pages = i
                if progress_callback:
                    progress_callback(progress)
                self.export_progress.emit(progress)
                
                # Copy page from source
                output_doc.insert_pdf(
                    source_doc,
                    from_page=page_num,
                    to_page=page_num,
                )
                
                # Add annotations if needed
                if annotations and options.annotation_mode != AnnotationExportMode.EXCLUDE:
                    page_annotations = [
                        a for a in annotations
                        if a.page_number == page_num
                    ]
                    
                    if page_annotations:
                        output_page = output_doc[-1]
                        self._add_annotations_to_page(
                            output_page,
                            page_annotations,
                            options.annotation_mode,
                        )
            
            # Set metadata
            if options.preserve_metadata:
                output_doc.set_metadata(source_doc.metadata)
            
            if options.custom_metadata:
                metadata = output_doc.metadata.copy()
                metadata.update(options.custom_metadata)
                output_doc.set_metadata(metadata)
            
            # Save options
            save_options = 0
            if options.compress:
                save_options |= fitz.PDF_OPT_COMPRESS
            if options.linearize:
                save_options |= fitz.PDF_OPT_LINEAR
            
            progress.current_stage = "Saving document"
            if progress_callback:
                progress_callback(progress)
            self.export_progress.emit(progress)
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save document
            output_doc.save(str(output_path), deflate=options.compress)
            output_doc.close()
            
            progress.processed_pages = len(pages)
            
            return Success(ExportResult(
                success=True,
                output_path=output_path,
                pages_exported=len(pages),
                file_size_bytes=output_path.stat().st_size,
            ))
            
        except Exception as e:
            return Failure(PDFError(
                message=f"PDF export failed: {e}",
            ))
    
    def _export_images(
        self,
        pdf_doc,
        output_path: Path,
        pages: List[int],
        annotations: Optional[List[AnnotationBase]],
        options: ExportOptions,
        progress: ExportProgress,
        progress_callback: Optional[Callable],
    ) -> Result[ExportResult]:
        """Export pages as images."""
        try:
            # Determine output format
            format_map = {
                ExportFormat.PNG: ("PNG", ".png"),
                ExportFormat.JPEG: ("JPEG", ".jpg"),
                ExportFormat.TIFF: ("TIFF", ".tiff"),
            }
            
            img_format, extension = format_map.get(
                options.format,
                ("PNG", ".png")
            )
            
            output_paths = []
            
            # Ensure output directory exists
            output_dir = output_path.parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Calculate zoom from DPI (72 DPI is standard for PDF)
            zoom = options.dpi / 72.0
            
            for i, page_num in enumerate(pages):
                if self._cancel_requested:
                    progress.is_cancelled = True
                    return Success(ExportResult(
                        success=False,
                        output_paths=output_paths,
                        error_message="Export cancelled",
                    ))
                
                progress.current_stage = f"Rendering page {i + 1}/{len(pages)}"
                progress.processed_pages = i
                if progress_callback:
                    progress_callback(progress)
                self.export_progress.emit(progress)
                
                # Render page
                render_result = pdf_doc.render_page(
                    page_num,
                    zoom=zoom,
                )
                
                if render_result.is_failure:
                    continue
                
                pixmap = render_result.value
                
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
                
                # Draw annotations if needed
                if annotations and options.annotation_mode != AnnotationExportMode.EXCLUDE:
                    page_annotations = [
                        a for a in annotations
                        if a.page_number == page_num
                    ]
                    
                    if page_annotations:
                        qimage = self._render_annotations_on_image(
                            qimage,
                            page_annotations,
                            zoom,
                        )
                
                # Determine output filename
                if len(pages) == 1:
                    img_path = output_path.with_suffix(extension)
                else:
                    img_path = output_dir / f"{output_path.stem}_{page_num + 1:04d}{extension}"
                
                # Save image
                if img_format == "JPEG":
                    qimage.save(str(img_path), img_format, options.image_quality)
                else:
                    qimage.save(str(img_path), img_format)
                
                output_paths.append(img_path)
            
            progress.processed_pages = len(pages)
            
            total_size = sum(p.stat().st_size for p in output_paths)
            
            return Success(ExportResult(
                success=True,
                output_path=output_paths[0] if len(output_paths) == 1 else None,
                output_paths=output_paths,
                pages_exported=len(output_paths),
                file_size_bytes=total_size,
            ))
            
        except Exception as e:
            return Failure(PDFError(
                message=f"Image export failed: {e}",
            ))
    
    def _add_annotations_to_page(
        self,
        page,
        annotations: List[AnnotationBase],
        mode: AnnotationExportMode,
    ) -> None:
        """Add annotations to a PDF page."""
        import fitz
        
        for annotation in annotations:
            try:
                if mode == AnnotationExportMode.FLATTEN:
                    # Draw annotation directly onto page content
                    self._flatten_annotation(page, annotation)
                else:
                    # Create PDF annotation object
                    self._create_pdf_annotation(page, annotation)
            except Exception:
                # Skip problematic annotations
                pass
    
    def _flatten_annotation(self, page, annotation: AnnotationBase) -> None:
        """Render annotation directly onto page content."""
        import fitz
        
        # This would need specific implementation for each annotation type
        # For now, this is a simplified version
        
        from models.annotation import (
            TextAnnotation,
            FreehandDrawing,
            RectangleAnnotation,
            EllipseAnnotation,
            LineAnnotation,
            ArrowAnnotation,
            StickyNoteAnnotation,
            TextHighlightAnnotation,
        )
        
        if isinstance(annotation, TextAnnotation):
            # Draw text
            rect = fitz.Rect(
                annotation.bounds.x,
                annotation.bounds.y,
                annotation.bounds.x + annotation.bounds.width,
                annotation.bounds.y + annotation.bounds.height,
            )
            color = (
                annotation.color.r / 255,
                annotation.color.g / 255,
                annotation.color.b / 255,
            )
            page.insert_textbox(
                rect,
                annotation.content,
                fontsize=annotation.font_size,
                color=color,
            )
        
        elif isinstance(annotation, FreehandDrawing):
            # Draw path
            if annotation.points:
                color = (
                    annotation.stroke_style.color.r / 255,
                    annotation.stroke_style.color.g / 255,
                    annotation.stroke_style.color.b / 255,
                )
                shape = page.new_shape()
                
                points = [(p.x, p.y) for p in annotation.points]
                if len(points) > 1:
                    shape.draw_polyline(points)
                    shape.finish(
                        color=color,
                        width=annotation.stroke_style.width,
                    )
                    shape.commit()
        
        elif isinstance(annotation, RectangleAnnotation):
            rect = fitz.Rect(
                annotation.bounds.x,
                annotation.bounds.y,
                annotation.bounds.x + annotation.bounds.width,
                annotation.bounds.y + annotation.bounds.height,
            )
            stroke_color = (
                annotation.stroke_style.color.r / 255,
                annotation.stroke_style.color.g / 255,
                annotation.stroke_style.color.b / 255,
            )
            shape = page.new_shape()
            shape.draw_rect(rect)
            
            fill_color = None
            if annotation.fill_style and annotation.fill_style.enabled:
                fill_color = (
                    annotation.fill_style.color.r / 255,
                    annotation.fill_style.color.g / 255,
                    annotation.fill_style.color.b / 255,
                )
            
            shape.finish(
                color=stroke_color,
                fill=fill_color,
                width=annotation.stroke_style.width,
            )
            shape.commit()
        
        elif isinstance(annotation, TextHighlightAnnotation):
            # Draw highlight rectangles
            for quad in annotation.quads:
                rect = fitz.Rect(quad)
                color = (
                    annotation.color.r / 255,
                    annotation.color.g / 255,
                    annotation.color.b / 255,
                )
                shape = page.new_shape()
                shape.draw_rect(rect)
                shape.finish(fill=color, color=None)
                shape.commit()
    
    def _create_pdf_annotation(self, page, annotation: AnnotationBase) -> None:
        """Create a PDF annotation object."""
        import fitz
        
        from models.annotation import (
            TextAnnotation,
            StickyNoteAnnotation,
            TextHighlightAnnotation,
        )
        
        if isinstance(annotation, StickyNoteAnnotation):
            point = fitz.Point(annotation.position.x, annotation.position.y)
            annot = page.add_text_annot(point, annotation.content)
            if annotation.color:
                annot.set_colors(stroke=(
                    annotation.color.r / 255,
                    annotation.color.g / 255,
                    annotation.color.b / 255,
                ))
            annot.update()
        
        elif isinstance(annotation, TextHighlightAnnotation):
            for quad in annotation.quads:
                rect = fitz.Rect(quad)
                annot = page.add_highlight_annot(rect)
                if annotation.color:
                    annot.set_colors(stroke=(
                        annotation.color.r / 255,
                        annotation.color.g / 255,
                        annotation.color.b / 255,
                    ))
                annot.update()
    
    def _render_annotations_on_image(
        self,
        image: QImage,
        annotations: List[AnnotationBase],
        zoom: float,
    ) -> QImage:
        """Render annotations onto a QImage."""
        from PyQt6.QtCore import Qt, QPointF, QRectF
        from PyQt6.QtGui import QPen, QBrush, QColor, QFont
        
        # Create a copy to draw on
        result = image.copy()
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        from models.annotation import (
            TextAnnotation,
            FreehandDrawing,
            RectangleAnnotation,
            EllipseAnnotation,
            LineAnnotation,
            ArrowAnnotation,
            StickyNoteAnnotation,
            TextHighlightAnnotation,
        )
        
        for annotation in annotations:
            try:
                if isinstance(annotation, FreehandDrawing):
                    if annotation.points:
                        color = QColor(
                            annotation.stroke_style.color.r,
                            annotation.stroke_style.color.g,
                            annotation.stroke_style.color.b,
                            int(annotation.stroke_style.color.a * 255),
                        )
                        pen = QPen(color)
                        pen.setWidthF(annotation.stroke_style.width * zoom)
                        painter.setPen(pen)
                        
                        for i in range(1, len(annotation.points)):
                            p1 = annotation.points[i - 1]
                            p2 = annotation.points[i]
                            painter.drawLine(
                                QPointF(p1.x * zoom, p1.y * zoom),
                                QPointF(p2.x * zoom, p2.y * zoom),
                            )
                
                elif isinstance(annotation, RectangleAnnotation):
                    rect = QRectF(
                        annotation.bounds.x * zoom,
                        annotation.bounds.y * zoom,
                        annotation.bounds.width * zoom,
                        annotation.bounds.height * zoom,
                    )
                    
                    stroke_color = QColor(
                        annotation.stroke_style.color.r,
                        annotation.stroke_style.color.g,
                        annotation.stroke_style.color.b,
                    )
                    pen = QPen(stroke_color)
                    pen.setWidthF(annotation.stroke_style.width * zoom)
                    painter.setPen(pen)
                    
                    if annotation.fill_style and annotation.fill_style.enabled:
                        fill_color = QColor(
                            annotation.fill_style.color.r,
                            annotation.fill_style.color.g,
                            annotation.fill_style.color.b,
                            int(annotation.fill_style.color.a * 255),
                        )
                        painter.setBrush(QBrush(fill_color))
                    else:
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                    
                    if annotation.corner_radius > 0:
                        painter.drawRoundedRect(
                            rect,
                            annotation.corner_radius * zoom,
                            annotation.corner_radius * zoom,
                        )
                    else:
                        painter.drawRect(rect)
                
                elif isinstance(annotation, TextAnnotation):
                    color = QColor(
                        annotation.color.r,
                        annotation.color.g,
                        annotation.color.b,
                    )
                    painter.setPen(QPen(color))
                    
                    font = QFont(annotation.font_family)
                    font.setPointSizeF(annotation.font_size * zoom)
                    font.setBold(annotation.bold)
                    font.setItalic(annotation.italic)
                    painter.setFont(font)
                    
                    rect = QRectF(
                        annotation.bounds.x * zoom,
                        annotation.bounds.y * zoom,
                        annotation.bounds.width * zoom,
                        annotation.bounds.height * zoom,
                    )
                    painter.drawText(rect, Qt.TextFlag.TextWordWrap, annotation.content)
                
                elif isinstance(annotation, TextHighlightAnnotation):
                    color = QColor(
                        annotation.color.r,
                        annotation.color.g,
                        annotation.color.b,
                        100,  # Semi-transparent
                    )
                    painter.setBrush(QBrush(color))
                    painter.setPen(Qt.PenStyle.NoPen)
                    
                    for quad in annotation.quads:
                        rect = QRectF(
                            quad[0] * zoom,
                            quad[1] * zoom,
                            (quad[2] - quad[0]) * zoom,
                            (quad[3] - quad[1]) * zoom,
                        )
                        painter.drawRect(rect)
                        
            except Exception:
                # Skip problematic annotations
                pass
        
        painter.end()
        return result
