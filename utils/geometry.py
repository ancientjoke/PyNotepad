from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional
import math

from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QTransform


@dataclass(frozen=True)
class Point2D:
    """Simple 2D point for geometry calculations."""
    x: float
    y: float
    
    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)
    
    def to_qpointf(self) -> QPointF:
        return QPointF(self.x, self.y)


@dataclass(frozen=True)
class Rect2D:
    """Simple 2D rectangle for geometry calculations."""
    x: float
    y: float
    width: float
    height: float
    
    def to_tuple(self) -> Tuple[float, float, float, float]:
        return (self.x, self.y, self.width, self.height)
    
    def to_qrectf(self) -> QRectF:
        return QRectF(self.x, self.y, self.width, self.height)


class CoordinateTransformer:
    """
    Handles coordinate transformations between PDF space and screen space.
    PDF coordinates have origin at bottom-left with Y increasing upward.
    Screen coordinates have origin at top-left with Y increasing downward.
    """
    
    def __init__(
        self,
        page_width: float,
        page_height: float,
        scale: float = 1.0,
        rotation: int = 0,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ):
        self._page_width = page_width
        self._page_height = page_height
        self._scale = scale
        self._rotation = rotation % 360
        self._offset_x = offset_x
        self._offset_y = offset_y
        
        self._transform = self._build_transform()
        self._inverse_transform = self._build_inverse_transform()
    
    def _build_transform(self) -> QTransform:
        """Build the PDF to screen transformation matrix."""
        transform = QTransform()
        
        transform.translate(self._offset_x, self._offset_y)
        
        transform.scale(self._scale, self._scale)
        
        if self._rotation == 90:
            transform.rotate(90)
            transform.translate(0, -self._page_height)
        elif self._rotation == 180:
            transform.rotate(180)
            transform.translate(-self._page_width, -self._page_height)
        elif self._rotation == 270:
            transform.rotate(270)
            transform.translate(-self._page_width, 0)
        
        transform.scale(1, -1)
        transform.translate(0, -self._page_height)
        
        return transform
    
    def _build_inverse_transform(self) -> QTransform:
        """Build the screen to PDF transformation matrix."""
        inverted, success = self._transform.inverted()
        if not success:
            return QTransform()
        return inverted
    
    def pdf_to_screen(self, point: Point2D) -> Point2D:
        """Transform a point from PDF coordinates to screen coordinates."""
        qt_point = self._transform.map(point.to_qpointf())
        return Point2D(qt_point.x(), qt_point.y())
    
    def screen_to_pdf(self, point: Point2D) -> Point2D:
        """Transform a point from screen coordinates to PDF coordinates."""
        qt_point = self._inverse_transform.map(point.to_qpointf())
        return Point2D(qt_point.x(), qt_point.y())
    
    def pdf_rect_to_screen(self, rect: Rect2D) -> Rect2D:
        """Transform a rectangle from PDF coordinates to screen coordinates."""
        top_left = self.pdf_to_screen(Point2D(rect.x, rect.y + rect.height))
        bottom_right = self.pdf_to_screen(Point2D(rect.x + rect.width, rect.y))
        
        min_x = min(top_left.x, bottom_right.x)
        min_y = min(top_left.y, bottom_right.y)
        max_x = max(top_left.x, bottom_right.x)
        max_y = max(top_left.y, bottom_right.y)
        
        return Rect2D(min_x, min_y, max_x - min_x, max_y - min_y)
    
    def screen_rect_to_pdf(self, rect: Rect2D) -> Rect2D:
        """Transform a rectangle from screen coordinates to PDF coordinates."""
        top_left = self.screen_to_pdf(Point2D(rect.x, rect.y))
        bottom_right = self.screen_to_pdf(Point2D(rect.x + rect.width, rect.y + rect.height))
        
        min_x = min(top_left.x, bottom_right.x)
        min_y = min(top_left.y, bottom_right.y)
        max_x = max(top_left.x, bottom_right.x)
        max_y = max(top_left.y, bottom_right.y)
        
        return Rect2D(min_x, min_y, max_x - min_x, max_y - min_y)
    
    def scale_distance(self, distance: float) -> float:
        """Scale a distance value from PDF to screen space."""
        return distance * self._scale
    
    def unscale_distance(self, distance: float) -> float:
        """Scale a distance value from screen to PDF space."""
        return distance / self._scale
    
    @property
    def effective_page_size(self) -> Tuple[float, float]:
        """Get the effective page size after rotation and scaling."""
        if self._rotation in (90, 270):
            return (
                self._page_height * self._scale,
                self._page_width * self._scale,
            )
        return (
            self._page_width * self._scale,
            self._page_height * self._scale,
        )
    
    def with_scale(self, new_scale: float) -> CoordinateTransformer:
        """Create a new transformer with different scale."""
        return CoordinateTransformer(
            self._page_width,
            self._page_height,
            new_scale,
            self._rotation,
            self._offset_x,
            self._offset_y,
        )
    
    def with_rotation(self, new_rotation: int) -> CoordinateTransformer:
        """Create a new transformer with different rotation."""
        return CoordinateTransformer(
            self._page_width,
            self._page_height,
            self._scale,
            new_rotation,
            self._offset_x,
            self._offset_y,
        )
    
    def with_offset(self, offset_x: float, offset_y: float) -> CoordinateTransformer:
        """Create a new transformer with different offset."""
        return CoordinateTransformer(
            self._page_width,
            self._page_height,
            self._scale,
            self._rotation,
            offset_x,
            offset_y,
        )


def scale_point(point: Tuple[float, float], scale: float) -> Tuple[float, float]:
    """Scale a point by a factor."""
    return (point[0] * scale, point[1] * scale)


def scale_rectangle(
    rect: Tuple[float, float, float, float],
    scale: float,
) -> Tuple[float, float, float, float]:
    """Scale a rectangle (x, y, width, height) by a factor."""
    return (
        rect[0] * scale,
        rect[1] * scale,
        rect[2] * scale,
        rect[3] * scale,
    )


def rotate_point(
    point: Tuple[float, float],
    center: Tuple[float, float],
    angle_degrees: float,
) -> Tuple[float, float]:
    """Rotate a point around a center by an angle in degrees."""
    angle_rad = math.radians(angle_degrees)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    
    translated_x = point[0] - center[0]
    translated_y = point[1] - center[1]
    
    rotated_x = translated_x * cos_a - translated_y * sin_a
    rotated_y = translated_x * sin_a + translated_y * cos_a
    
    return (rotated_x + center[0], rotated_y + center[1])


def points_to_bounding_rect(
    points: List[Tuple[float, float]],
    padding: float = 0.0,
) -> Tuple[float, float, float, float]:
    """Calculate the bounding rectangle for a list of points."""
    if not points:
        return (0.0, 0.0, 0.0, 0.0)
    
    min_x = min(p[0] for p in points) - padding
    max_x = max(p[0] for p in points) + padding
    min_y = min(p[1] for p in points) - padding
    max_y = max(p[1] for p in points) + padding
    
    return (min_x, min_y, max_x - min_x, max_y - min_y)


def line_intersection(
    line1_start: Tuple[float, float],
    line1_end: Tuple[float, float],
    line2_start: Tuple[float, float],
    line2_end: Tuple[float, float],
) -> Optional[Tuple[float, float]]:
    """
    Calculate the intersection point of two line segments.
    Returns None if lines don't intersect or are parallel.
    """
    x1, y1 = line1_start
    x2, y2 = line1_end
    x3, y3 = line2_start
    x4, y4 = line2_end
    
    denominator = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    
    if abs(denominator) < 1e-10:
        return None
    
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denominator
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denominator
    
    if 0 <= t <= 1 and 0 <= u <= 1:
        intersection_x = x1 + t * (x2 - x1)
        intersection_y = y1 + t * (y2 - y1)
        return (intersection_x, intersection_y)
    
    return None


def point_distance(
    point1: Tuple[float, float],
    point2: Tuple[float, float],
) -> float:
    """Calculate the Euclidean distance between two points."""
    dx = point2[0] - point1[0]
    dy = point2[1] - point1[1]
    return math.sqrt(dx * dx + dy * dy)


def smooth_path_points(
    points: List[Tuple[float, float]],
    smoothing_factor: float = 0.5,
) -> List[Tuple[float, float]]:
    """
    Apply smoothing to a path of points using a simple moving average.
    
    Args:
        points: List of (x, y) points.
        smoothing_factor: Factor between 0 (no smoothing) and 1 (maximum smoothing).
    
    Returns:
        List of smoothed (x, y) points.
    """
    if len(points) < 3:
        return points
    
    smoothing_factor = max(0.0, min(1.0, smoothing_factor))
    
    smoothed = [points[0]]
    
    for i in range(1, len(points) - 1):
        prev_point = points[i - 1]
        current_point = points[i]
        next_point = points[i + 1]
        
        avg_x = (prev_point[0] + current_point[0] + next_point[0]) / 3
        avg_y = (prev_point[1] + current_point[1] + next_point[1]) / 3
        
        smoothed_x = current_point[0] + smoothing_factor * (avg_x - current_point[0])
        smoothed_y = current_point[1] + smoothing_factor * (avg_y - current_point[1])
        
        smoothed.append((smoothed_x, smoothed_y))
    
    smoothed.append(points[-1])
    
    return smoothed


def calculate_arrow_head_points(
    start: Tuple[float, float],
    end: Tuple[float, float],
    head_length: float = 15.0,
    head_angle: float = 30.0,
) -> List[Tuple[float, float]]:
    """
    Calculate the points for an arrow head.
    
    Args:
        start: Arrow start point.
        end: Arrow end point (tip of arrow).
        head_length: Length of arrow head.
        head_angle: Angle of arrow head in degrees.
    
    Returns:
        List of three points: [left_point, tip_point, right_point].
    """
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.sqrt(dx * dx + dy * dy)
    
    if length < 1e-10:
        return [end, end, end]
    
    unit_dx = dx / length
    unit_dy = dy / length
    
    base_x = end[0] - unit_dx * head_length
    base_y = end[1] - unit_dy * head_length
    
    angle_rad = math.radians(head_angle)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    
    perp_dx = -unit_dy
    perp_dy = unit_dx
    
    left_x = base_x + perp_dx * head_length * math.tan(angle_rad)
    left_y = base_y + perp_dy * head_length * math.tan(angle_rad)
    
    right_x = base_x - perp_dx * head_length * math.tan(angle_rad)
    right_y = base_y - perp_dy * head_length * math.tan(angle_rad)
    
    return [(left_x, left_y), end, (right_x, right_y)]


def point_to_line_distance(
    point: Tuple[float, float],
    line_start: Tuple[float, float],
    line_end: Tuple[float, float],
) -> float:
    """Calculate the perpendicular distance from a point to a line segment."""
    px, py = point
    x1, y1 = line_start
    x2, y2 = line_end
    
    dx = x2 - x1
    dy = y2 - y1
    
    length_squared = dx * dx + dy * dy
    
    if length_squared < 1e-10:
        return point_distance(point, line_start)
    
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / length_squared))
    
    projection_x = x1 + t * dx
    projection_y = y1 + t * dy
    
    return point_distance(point, (projection_x, projection_y))


def simplify_path(
    points: List[Tuple[float, float]],
    tolerance: float = 1.0,
) -> List[Tuple[float, float]]:
    """
    Simplify a path using the Ramer-Douglas-Peucker algorithm.
    
    Args:
        points: List of (x, y) points.
        tolerance: Maximum distance a point can be from the simplified path.
    
    Returns:
        Simplified list of points.
    """
    if len(points) < 3:
        return points
    
    max_distance = 0.0
    max_index = 0
    
    for i in range(1, len(points) - 1):
        distance = point_to_line_distance(points[i], points[0], points[-1])
        if distance > max_distance:
            max_distance = distance
            max_index = i
    
    if max_distance > tolerance:
        left_simplified = simplify_path(points[:max_index + 1], tolerance)
        right_simplified = simplify_path(points[max_index:], tolerance)
        
        return left_simplified[:-1] + right_simplified
    
    return [points[0], points[-1]]
