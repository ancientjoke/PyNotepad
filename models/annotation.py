from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Type
import json
import uuid


class AnnotationType(Enum):
    """Types of annotations supported by the application."""
    TEXT = auto()
    FREEHAND = auto()
    RECTANGLE = auto()
    ELLIPSE = auto()
    LINE = auto()
    ARROW = auto()
    STICKY_NOTE = auto()
    HIGHLIGHT = auto()
    STAMP = auto()
    AREA_SELECTION = auto()


@dataclass(frozen=True)
class Color:
    """Immutable RGBA color representation."""
    
    red: int = 0
    green: int = 0
    blue: int = 0
    alpha: int = 255
    
    def to_hex(self) -> str:
        """Convert to hex string (#RRGGBB or #RRGGBBAA)."""
        if self.alpha == 255:
            return f"#{self.red:02x}{self.green:02x}{self.blue:02x}"
        return f"#{self.red:02x}{self.green:02x}{self.blue:02x}{self.alpha:02x}"
    
    def to_rgba_tuple(self) -> Tuple[int, int, int, int]:
        """Convert to RGBA tuple."""
        return (self.red, self.green, self.blue, self.alpha)
    
    @classmethod
    def from_hex(cls, hex_string: str) -> Color:
        """Create color from hex string."""
        hex_string = hex_string.lstrip("#")
        if len(hex_string) == 6:
            return cls(
                red=int(hex_string[0:2], 16),
                green=int(hex_string[2:4], 16),
                blue=int(hex_string[4:6], 16),
            )
        elif len(hex_string) == 8:
            return cls(
                red=int(hex_string[0:2], 16),
                green=int(hex_string[2:4], 16),
                blue=int(hex_string[4:6], 16),
                alpha=int(hex_string[6:8], 16),
            )
        raise ValueError(f"Invalid hex color: {hex_string}")
    
    @classmethod
    def red_color(cls) -> Color:
        return cls(255, 0, 0)
    
    @classmethod
    def green_color(cls) -> Color:
        return cls(0, 255, 0)
    
    @classmethod
    def blue_color(cls) -> Color:
        return cls(0, 0, 255)
    
    @classmethod
    def yellow_color(cls) -> Color:
        return cls(255, 255, 0)
    
    @classmethod
    def black_color(cls) -> Color:
        return cls(0, 0, 0)
    
    @classmethod
    def white_color(cls) -> Color:
        return cls(255, 255, 255)
    
    def with_alpha(self, alpha: int) -> Color:
        """Create new color with different alpha."""
        return Color(self.red, self.green, self.blue, alpha)


@dataclass(frozen=True)
class Point:
    """Immutable 2D point in PDF coordinate space."""
    
    x: float
    y: float
    
    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)
    
    def offset(self, dx: float, dy: float) -> Point:
        return Point(self.x + dx, self.y + dy)
    
    def scale(self, factor: float) -> Point:
        return Point(self.x * factor, self.y * factor)


@dataclass(frozen=True)
class Rectangle:
    """Immutable rectangle in PDF coordinate space."""
    
    x: float
    y: float
    width: float
    height: float
    
    @property
    def x1(self) -> float:
        return self.x
    
    @property
    def y1(self) -> float:
        return self.y
    
    @property
    def x2(self) -> float:
        return self.x + self.width
    
    @property
    def y2(self) -> float:
        return self.y + self.height
    
    @property
    def center(self) -> Point:
        return Point(self.x + self.width / 2, self.y + self.height / 2)
    
    @property
    def top_left(self) -> Point:
        return Point(self.x, self.y)
    
    @property
    def bottom_right(self) -> Point:
        return Point(self.x + self.width, self.y + self.height)
    
    def to_tuple(self) -> Tuple[float, float, float, float]:
        return (self.x, self.y, self.width, self.height)
    
    def contains_point(self, point: Point) -> bool:
        return (
            self.x <= point.x <= self.x + self.width
            and self.y <= point.y <= self.y + self.height
        )
    
    def intersects(self, other: Rectangle) -> bool:
        return not (
            self.x2 < other.x1
            or other.x2 < self.x1
            or self.y2 < other.y1
            or other.y2 < self.y1
        )
    
    def scale(self, factor: float) -> Rectangle:
        return Rectangle(
            self.x * factor,
            self.y * factor,
            self.width * factor,
            self.height * factor,
        )


@dataclass(frozen=True)
class StrokeStyle:
    """Immutable stroke styling properties."""
    
    color: Color = field(default_factory=Color.black_color)
    width: float = 1.0
    dash_pattern: Optional[Tuple[float, ...]] = None
    line_cap: str = "round"
    line_join: str = "round"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "color": self.color.to_hex(),
            "width": self.width,
            "dash_pattern": self.dash_pattern,
            "line_cap": self.line_cap,
            "line_join": self.line_join,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StrokeStyle:
        return cls(
            color=Color.from_hex(data.get("color", "#000000")),
            width=data.get("width", 1.0),
            dash_pattern=tuple(data["dash_pattern"]) if data.get("dash_pattern") else None,
            line_cap=data.get("line_cap", "round"),
            line_join=data.get("line_join", "round"),
        )


@dataclass(frozen=True)
class FillStyle:
    """Immutable fill styling properties."""
    
    color: Color = field(default_factory=lambda: Color.white_color().with_alpha(0))
    
    def to_dict(self) -> Dict[str, Any]:
        return {"color": self.color.to_hex()}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FillStyle:
        return cls(color=Color.from_hex(data.get("color", "#ffffff00")))


@dataclass
class AnnotationBase(ABC):
    """Abstract base class for all annotation types."""
    
    annotation_uuid: str
    annotation_type: AnnotationType
    page_number: int
    bounds: Rectangle
    z_index: int = 0
    
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    created_by: Optional[str] = None
    
    is_visible: bool = True
    is_locked: bool = False
    is_selected: bool = False
    
    group_id: Optional[str] = None
    
    @abstractmethod
    def render_data(self) -> Dict[str, Any]:
        """Get data needed for rendering this annotation."""
        pass
    
    @abstractmethod
    def serialize(self) -> Dict[str, Any]:
        """Serialize annotation to dictionary for storage."""
        pass
    
    @classmethod
    @abstractmethod
    def deserialize(cls, data: Dict[str, Any]) -> AnnotationBase:
        """Deserialize annotation from dictionary."""
        pass
    
    def _base_serialize(self) -> Dict[str, Any]:
        """Serialize base annotation properties."""
        return {
            "annotation_uuid": self.annotation_uuid,
            "annotation_type": self.annotation_type.name,
            "page_number": self.page_number,
            "bounds": self.bounds.to_tuple(),
            "z_index": self.z_index,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "created_by": self.created_by,
            "is_visible": self.is_visible,
            "is_locked": self.is_locked,
            "group_id": self.group_id,
        }
    
    @classmethod
    def _base_deserialize(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize base annotation properties."""
        bounds_data = data["bounds"]
        return {
            "annotation_uuid": data["annotation_uuid"],
            "page_number": data["page_number"],
            "bounds": Rectangle(*bounds_data),
            "z_index": data.get("z_index", 0),
            "created_at": datetime.fromisoformat(data["created_at"]),
            "modified_at": datetime.fromisoformat(data["modified_at"]),
            "created_by": data.get("created_by"),
            "is_visible": data.get("is_visible", True),
            "is_locked": data.get("is_locked", False),
            "group_id": data.get("group_id"),
        }
    
    def update_bounds(self, new_bounds: Rectangle) -> None:
        """Update annotation bounds and modification time."""
        self.bounds = new_bounds
        self.modified_at = datetime.now()
    
    def contains_point(self, point: Point) -> bool:
        """Check if point is within annotation bounds."""
        return self.bounds.contains_point(point)


@dataclass
class TextAnnotation(AnnotationBase):
    """Text annotation with rich text support."""
    
    text_content: str = ""
    font_family: str = "Arial"
    font_size: float = 12.0
    font_color: Color = field(default_factory=Color.black_color)
    font_bold: bool = False
    font_italic: bool = False
    text_alignment: str = "left"
    background_color: Optional[Color] = None
    
    def __post_init__(self):
        self.annotation_type = AnnotationType.TEXT
    
    def render_data(self) -> Dict[str, Any]:
        return {
            "text": self.text_content,
            "font_family": self.font_family,
            "font_size": self.font_size,
            "font_color": self.font_color.to_rgba_tuple(),
            "bold": self.font_bold,
            "italic": self.font_italic,
            "alignment": self.text_alignment,
            "background": self.background_color.to_rgba_tuple() if self.background_color else None,
            "bounds": self.bounds.to_tuple(),
        }
    
    def serialize(self) -> Dict[str, Any]:
        data = self._base_serialize()
        data.update({
            "text_content": self.text_content,
            "font_family": self.font_family,
            "font_size": self.font_size,
            "font_color": self.font_color.to_hex(),
            "font_bold": self.font_bold,
            "font_italic": self.font_italic,
            "text_alignment": self.text_alignment,
            "background_color": self.background_color.to_hex() if self.background_color else None,
        })
        return data
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> TextAnnotation:
        base = cls._base_deserialize(data)
        return cls(
            **base,
            annotation_type=AnnotationType.TEXT,
            text_content=data.get("text_content", ""),
            font_family=data.get("font_family", "Arial"),
            font_size=data.get("font_size", 12.0),
            font_color=Color.from_hex(data.get("font_color", "#000000")),
            font_bold=data.get("font_bold", False),
            font_italic=data.get("font_italic", False),
            text_alignment=data.get("text_alignment", "left"),
            background_color=Color.from_hex(data["background_color"]) if data.get("background_color") else None,
        )


@dataclass
class FreehandDrawing(AnnotationBase):
    """Freehand drawing annotation with path points."""
    
    points: List[Point] = field(default_factory=list)
    stroke_style: StrokeStyle = field(default_factory=StrokeStyle)
    pressure_values: Optional[List[float]] = None
    smoothing_enabled: bool = True
    
    def __post_init__(self):
        self.annotation_type = AnnotationType.FREEHAND
    
    def add_point(self, point: Point, pressure: Optional[float] = None) -> None:
        """Add a point to the drawing path."""
        self.points.append(point)
        if pressure is not None and self.pressure_values is not None:
            self.pressure_values.append(pressure)
        self.modified_at = datetime.now()
        self._update_bounds()
    
    def _update_bounds(self) -> None:
        """Update bounds based on current points."""
        if not self.points:
            return
        
        min_x = min(p.x for p in self.points)
        max_x = max(p.x for p in self.points)
        min_y = min(p.y for p in self.points)
        max_y = max(p.y for p in self.points)
        
        padding = self.stroke_style.width / 2
        self.bounds = Rectangle(
            min_x - padding,
            min_y - padding,
            max_x - min_x + 2 * padding,
            max_y - min_y + 2 * padding,
        )
    
    def render_data(self) -> Dict[str, Any]:
        return {
            "points": [p.to_tuple() for p in self.points],
            "stroke": self.stroke_style.to_dict(),
            "pressure": self.pressure_values,
            "smoothing": self.smoothing_enabled,
        }
    
    def serialize(self) -> Dict[str, Any]:
        data = self._base_serialize()
        data.update({
            "points": [p.to_tuple() for p in self.points],
            "stroke_style": self.stroke_style.to_dict(),
            "pressure_values": self.pressure_values,
            "smoothing_enabled": self.smoothing_enabled,
        })
        return data
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> FreehandDrawing:
        base = cls._base_deserialize(data)
        return cls(
            **base,
            annotation_type=AnnotationType.FREEHAND,
            points=[Point(*p) for p in data.get("points", [])],
            stroke_style=StrokeStyle.from_dict(data.get("stroke_style", {})),
            pressure_values=data.get("pressure_values"),
            smoothing_enabled=data.get("smoothing_enabled", True),
        )


@dataclass
class RectangleAnnotation(AnnotationBase):
    """Rectangle shape annotation."""
    
    stroke_style: StrokeStyle = field(default_factory=StrokeStyle)
    fill_style: FillStyle = field(default_factory=FillStyle)
    corner_radius: float = 0.0
    
    def __post_init__(self):
        self.annotation_type = AnnotationType.RECTANGLE
    
    def render_data(self) -> Dict[str, Any]:
        return {
            "bounds": self.bounds.to_tuple(),
            "stroke": self.stroke_style.to_dict(),
            "fill": self.fill_style.to_dict(),
            "corner_radius": self.corner_radius,
        }
    
    def serialize(self) -> Dict[str, Any]:
        data = self._base_serialize()
        data.update({
            "stroke_style": self.stroke_style.to_dict(),
            "fill_style": self.fill_style.to_dict(),
            "corner_radius": self.corner_radius,
        })
        return data
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> RectangleAnnotation:
        base = cls._base_deserialize(data)
        return cls(
            **base,
            annotation_type=AnnotationType.RECTANGLE,
            stroke_style=StrokeStyle.from_dict(data.get("stroke_style", {})),
            fill_style=FillStyle.from_dict(data.get("fill_style", {})),
            corner_radius=data.get("corner_radius", 0.0),
        )


@dataclass
class EllipseAnnotation(AnnotationBase):
    """Ellipse shape annotation."""
    
    stroke_style: StrokeStyle = field(default_factory=StrokeStyle)
    fill_style: FillStyle = field(default_factory=FillStyle)
    
    def __post_init__(self):
        self.annotation_type = AnnotationType.ELLIPSE
    
    def render_data(self) -> Dict[str, Any]:
        return {
            "bounds": self.bounds.to_tuple(),
            "stroke": self.stroke_style.to_dict(),
            "fill": self.fill_style.to_dict(),
        }
    
    def serialize(self) -> Dict[str, Any]:
        data = self._base_serialize()
        data.update({
            "stroke_style": self.stroke_style.to_dict(),
            "fill_style": self.fill_style.to_dict(),
        })
        return data
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> EllipseAnnotation:
        base = cls._base_deserialize(data)
        return cls(
            **base,
            annotation_type=AnnotationType.ELLIPSE,
            stroke_style=StrokeStyle.from_dict(data.get("stroke_style", {})),
            fill_style=FillStyle.from_dict(data.get("fill_style", {})),
        )


@dataclass
class LineAnnotation(AnnotationBase):
    """Line annotation with start and end points."""
    
    start_point: Point = field(default_factory=lambda: Point(0, 0))
    end_point: Point = field(default_factory=lambda: Point(0, 0))
    stroke_style: StrokeStyle = field(default_factory=StrokeStyle)
    
    def __post_init__(self):
        self.annotation_type = AnnotationType.LINE
        self._update_bounds_from_points()
    
    def _update_bounds_from_points(self) -> None:
        """Update bounds based on start and end points."""
        min_x = min(self.start_point.x, self.end_point.x)
        max_x = max(self.start_point.x, self.end_point.x)
        min_y = min(self.start_point.y, self.end_point.y)
        max_y = max(self.start_point.y, self.end_point.y)
        
        padding = self.stroke_style.width / 2
        self.bounds = Rectangle(
            min_x - padding,
            min_y - padding,
            max_x - min_x + 2 * padding,
            max_y - min_y + 2 * padding,
        )
    
    def render_data(self) -> Dict[str, Any]:
        return {
            "start": self.start_point.to_tuple(),
            "end": self.end_point.to_tuple(),
            "stroke": self.stroke_style.to_dict(),
        }
    
    def serialize(self) -> Dict[str, Any]:
        data = self._base_serialize()
        data.update({
            "start_point": self.start_point.to_tuple(),
            "end_point": self.end_point.to_tuple(),
            "stroke_style": self.stroke_style.to_dict(),
        })
        return data
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> LineAnnotation:
        base = cls._base_deserialize(data)
        return cls(
            **base,
            annotation_type=AnnotationType.LINE,
            start_point=Point(*data.get("start_point", (0, 0))),
            end_point=Point(*data.get("end_point", (0, 0))),
            stroke_style=StrokeStyle.from_dict(data.get("stroke_style", {})),
        )


@dataclass
class ArrowAnnotation(AnnotationBase):
    """Arrow annotation with configurable head style."""
    
    start_point: Point = field(default_factory=lambda: Point(0, 0))
    end_point: Point = field(default_factory=lambda: Point(0, 0))
    stroke_style: StrokeStyle = field(default_factory=StrokeStyle)
    head_length: float = 15.0
    head_angle: float = 30.0
    head_filled: bool = True
    double_headed: bool = False
    
    def __post_init__(self):
        self.annotation_type = AnnotationType.ARROW
        self._update_bounds_from_points()
    
    def _update_bounds_from_points(self) -> None:
        """Update bounds based on start and end points with arrow head padding."""
        min_x = min(self.start_point.x, self.end_point.x)
        max_x = max(self.start_point.x, self.end_point.x)
        min_y = min(self.start_point.y, self.end_point.y)
        max_y = max(self.start_point.y, self.end_point.y)
        
        padding = max(self.stroke_style.width, self.head_length)
        self.bounds = Rectangle(
            min_x - padding,
            min_y - padding,
            max_x - min_x + 2 * padding,
            max_y - min_y + 2 * padding,
        )
    
    def render_data(self) -> Dict[str, Any]:
        return {
            "start": self.start_point.to_tuple(),
            "end": self.end_point.to_tuple(),
            "stroke": self.stroke_style.to_dict(),
            "head_length": self.head_length,
            "head_angle": self.head_angle,
            "head_filled": self.head_filled,
            "double_headed": self.double_headed,
        }
    
    def serialize(self) -> Dict[str, Any]:
        data = self._base_serialize()
        data.update({
            "start_point": self.start_point.to_tuple(),
            "end_point": self.end_point.to_tuple(),
            "stroke_style": self.stroke_style.to_dict(),
            "head_length": self.head_length,
            "head_angle": self.head_angle,
            "head_filled": self.head_filled,
            "double_headed": self.double_headed,
        })
        return data
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> ArrowAnnotation:
        base = cls._base_deserialize(data)
        return cls(
            **base,
            annotation_type=AnnotationType.ARROW,
            start_point=Point(*data.get("start_point", (0, 0))),
            end_point=Point(*data.get("end_point", (0, 0))),
            stroke_style=StrokeStyle.from_dict(data.get("stroke_style", {})),
            head_length=data.get("head_length", 15.0),
            head_angle=data.get("head_angle", 30.0),
            head_filled=data.get("head_filled", True),
            double_headed=data.get("double_headed", False),
        )


@dataclass
class StickyNoteAnnotation(AnnotationBase):
    """Sticky note annotation with collapsible comment."""
    
    note_content: str = ""
    author: str = ""
    is_collapsed: bool = True
    note_color: Color = field(default_factory=Color.yellow_color)
    icon_type: str = "comment"
    
    def __post_init__(self):
        self.annotation_type = AnnotationType.STICKY_NOTE
    
    def render_data(self) -> Dict[str, Any]:
        return {
            "position": self.bounds.top_left.to_tuple(),
            "content": self.note_content,
            "author": self.author,
            "collapsed": self.is_collapsed,
            "color": self.note_color.to_rgba_tuple(),
            "icon": self.icon_type,
            "created": self.created_at.isoformat(),
        }
    
    def serialize(self) -> Dict[str, Any]:
        data = self._base_serialize()
        data.update({
            "note_content": self.note_content,
            "author": self.author,
            "is_collapsed": self.is_collapsed,
            "note_color": self.note_color.to_hex(),
            "icon_type": self.icon_type,
        })
        return data
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> StickyNoteAnnotation:
        base = cls._base_deserialize(data)
        return cls(
            **base,
            annotation_type=AnnotationType.STICKY_NOTE,
            note_content=data.get("note_content", ""),
            author=data.get("author", ""),
            is_collapsed=data.get("is_collapsed", True),
            note_color=Color.from_hex(data.get("note_color", "#ffff00")),
            icon_type=data.get("icon_type", "comment"),
        )


@dataclass
class TextHighlightAnnotation(AnnotationBase):
    """Text highlight annotation with blend mode support."""
    
    highlight_color: Color = field(default_factory=lambda: Color.yellow_color().with_alpha(128))
    highlight_rects: List[Rectangle] = field(default_factory=list)
    blend_mode: str = "multiply"
    
    def __post_init__(self):
        self.annotation_type = AnnotationType.HIGHLIGHT
    
    def add_rect(self, rect: Rectangle) -> None:
        """Add a highlight rectangle."""
        self.highlight_rects.append(rect)
        self.modified_at = datetime.now()
        self._update_bounds()
    
    def _update_bounds(self) -> None:
        """Update bounds to encompass all highlight rects."""
        if not self.highlight_rects:
            return
        
        min_x = min(r.x for r in self.highlight_rects)
        max_x = max(r.x + r.width for r in self.highlight_rects)
        min_y = min(r.y for r in self.highlight_rects)
        max_y = max(r.y + r.height for r in self.highlight_rects)
        
        self.bounds = Rectangle(min_x, min_y, max_x - min_x, max_y - min_y)
    
    def render_data(self) -> Dict[str, Any]:
        return {
            "color": self.highlight_color.to_rgba_tuple(),
            "rects": [r.to_tuple() for r in self.highlight_rects],
            "blend_mode": self.blend_mode,
        }
    
    def serialize(self) -> Dict[str, Any]:
        data = self._base_serialize()
        data.update({
            "highlight_color": self.highlight_color.to_hex(),
            "highlight_rects": [r.to_tuple() for r in self.highlight_rects],
            "blend_mode": self.blend_mode,
        })
        return data
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> TextHighlightAnnotation:
        base = cls._base_deserialize(data)
        return cls(
            **base,
            annotation_type=AnnotationType.HIGHLIGHT,
            highlight_color=Color.from_hex(data.get("highlight_color", "#ffff0080")),
            highlight_rects=[Rectangle(*r) for r in data.get("highlight_rects", [])],
            blend_mode=data.get("blend_mode", "multiply"),
        )


@dataclass
class StampAnnotation(AnnotationBase):
    """Stamp annotation with image or predefined stamp types."""
    
    stamp_type: str = "custom"
    stamp_text: Optional[str] = None
    image_data: Optional[bytes] = None
    image_path: Optional[Path] = None
    opacity: float = 1.0
    
    def __post_init__(self):
        self.annotation_type = AnnotationType.STAMP
    
    def render_data(self) -> Dict[str, Any]:
        return {
            "bounds": self.bounds.to_tuple(),
            "stamp_type": self.stamp_type,
            "text": self.stamp_text,
            "image_path": str(self.image_path) if self.image_path else None,
            "opacity": self.opacity,
        }
    
    def serialize(self) -> Dict[str, Any]:
        data = self._base_serialize()
        data.update({
            "stamp_type": self.stamp_type,
            "stamp_text": self.stamp_text,
            "image_path": str(self.image_path) if self.image_path else None,
            "opacity": self.opacity,
        })
        return data
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> StampAnnotation:
        base = cls._base_deserialize(data)
        image_path = Path(data["image_path"]) if data.get("image_path") else None
        return cls(
            **base,
            annotation_type=AnnotationType.STAMP,
            stamp_type=data.get("stamp_type", "custom"),
            stamp_text=data.get("stamp_text"),
            image_path=image_path,
            opacity=data.get("opacity", 1.0),
        )


@dataclass
class AreaSelectionAnnotation(AnnotationBase):
    """Area selection annotation with dimension display."""
    
    stroke_style: StrokeStyle = field(default_factory=lambda: StrokeStyle(
        color=Color.blue_color(),
        width=2.0,
        dash_pattern=(5.0, 5.0),
    ))
    fill_style: FillStyle = field(default_factory=lambda: FillStyle(
        color=Color.blue_color().with_alpha(32)
    ))
    show_dimensions: bool = True
    label: Optional[str] = None
    
    def __post_init__(self):
        self.annotation_type = AnnotationType.AREA_SELECTION
    
    @property
    def area(self) -> float:
        """Calculate area in PDF points squared."""
        return self.bounds.width * self.bounds.height
    
    @property
    def perimeter(self) -> float:
        """Calculate perimeter in PDF points."""
        return 2 * (self.bounds.width + self.bounds.height)
    
    def render_data(self) -> Dict[str, Any]:
        return {
            "bounds": self.bounds.to_tuple(),
            "stroke": self.stroke_style.to_dict(),
            "fill": self.fill_style.to_dict(),
            "show_dimensions": self.show_dimensions,
            "label": self.label,
            "width": self.bounds.width,
            "height": self.bounds.height,
        }
    
    def serialize(self) -> Dict[str, Any]:
        data = self._base_serialize()
        data.update({
            "stroke_style": self.stroke_style.to_dict(),
            "fill_style": self.fill_style.to_dict(),
            "show_dimensions": self.show_dimensions,
            "label": self.label,
        })
        return data
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> AreaSelectionAnnotation:
        base = cls._base_deserialize(data)
        return cls(
            **base,
            annotation_type=AnnotationType.AREA_SELECTION,
            stroke_style=StrokeStyle.from_dict(data.get("stroke_style", {})),
            fill_style=FillStyle.from_dict(data.get("fill_style", {})),
            show_dimensions=data.get("show_dimensions", True),
            label=data.get("label"),
        )


class AnnotationFactory:
    """Factory for creating annotation instances."""
    
    _type_map: Dict[str, Type[AnnotationBase]] = {
        AnnotationType.TEXT.name: TextAnnotation,
        AnnotationType.FREEHAND.name: FreehandDrawing,
        AnnotationType.RECTANGLE.name: RectangleAnnotation,
        AnnotationType.ELLIPSE.name: EllipseAnnotation,
        AnnotationType.LINE.name: LineAnnotation,
        AnnotationType.ARROW.name: ArrowAnnotation,
        AnnotationType.STICKY_NOTE.name: StickyNoteAnnotation,
        AnnotationType.HIGHLIGHT.name: TextHighlightAnnotation,
        AnnotationType.STAMP.name: StampAnnotation,
        AnnotationType.AREA_SELECTION.name: AreaSelectionAnnotation,
    }
    
    @classmethod
    def create(
        cls,
        annotation_type: AnnotationType,
        page_number: int,
        bounds: Rectangle,
        **kwargs,
    ) -> AnnotationBase:
        """
        Create a new annotation of the specified type.
        
        Args:
            annotation_type: Type of annotation to create.
            page_number: Page number for the annotation.
            bounds: Initial bounding rectangle.
            **kwargs: Additional type-specific parameters.
        
        Returns:
            New annotation instance.
        """
        annotation_class = cls._type_map.get(annotation_type.name)
        if annotation_class is None:
            raise ValueError(f"Unknown annotation type: {annotation_type}")
        
        annotation_uuid = str(uuid.uuid4())
        
        return annotation_class(
            annotation_uuid=annotation_uuid,
            annotation_type=annotation_type,
            page_number=page_number,
            bounds=bounds,
            **kwargs,
        )
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> AnnotationBase:
        """
        Deserialize an annotation from dictionary data.
        
        Args:
            data: Dictionary containing serialized annotation.
        
        Returns:
            Deserialized annotation instance.
        """
        type_name = data.get("annotation_type")
        annotation_class = cls._type_map.get(type_name)
        if annotation_class is None:
            raise ValueError(f"Unknown annotation type: {type_name}")
        
        return annotation_class.deserialize(data)
    
    @classmethod
    def serialize_list(cls, annotations: List[AnnotationBase]) -> str:
        """Serialize a list of annotations to JSON string."""
        return json.dumps([ann.serialize() for ann in annotations])
    
    @classmethod
    def deserialize_list(cls, json_string: str) -> List[AnnotationBase]:
        """Deserialize annotations from JSON string."""
        data_list = json.loads(json_string)
        return [cls.deserialize(data) for data in data_list]
