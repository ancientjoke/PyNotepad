from __future__ import annotations
from pathlib import Path
from typing import Tuple, Optional
import re

from core.error_types import (
    Result,
    Success,
    Failure,
    ValidationError,
)


def validate_file_path(
    file_path: str | Path,
    must_exist: bool = True,
    allowed_extensions: Optional[list[str]] = None,
) -> Result[Path]:
    """
    Validate a file path.
    
    Args:
        file_path: Path to validate.
        must_exist: Whether the file must exist.
        allowed_extensions: List of allowed extensions (e.g., ['.pdf']).
    
    Returns:
        Result containing the validated Path or validation error.
    """
    try:
        path = Path(file_path).resolve()
    except Exception:
        return Failure(ValidationError(
            message="Invalid path format",
            field_name="file_path",
            invalid_value=str(file_path),
        ))
    
    if must_exist and not path.exists():
        return Failure(ValidationError(
            message="File does not exist",
            field_name="file_path",
            invalid_value=str(file_path),
        ))
    
    if must_exist and not path.is_file():
        return Failure(ValidationError(
            message="Path is not a file",
            field_name="file_path",
            invalid_value=str(file_path),
        ))
    
    if allowed_extensions:
        normalized_extensions = [ext.lower() if ext.startswith('.') else f'.{ext.lower()}' 
                                 for ext in allowed_extensions]
        if path.suffix.lower() not in normalized_extensions:
            return Failure(ValidationError(
                message=f"Invalid file extension. Allowed: {', '.join(normalized_extensions)}",
                field_name="file_path",
                invalid_value=path.suffix,
            ))
    
    return Success(path)


def validate_page_number(
    page_number: int,
    total_pages: int,
    zero_based: bool = True,
) -> Result[int]:
    """
    Validate a page number.
    
    Args:
        page_number: Page number to validate.
        total_pages: Total number of pages in the document.
        zero_based: Whether page numbering is zero-based.
    
    Returns:
        Result containing the validated page number.
    """
    min_page = 0 if zero_based else 1
    max_page = total_pages - 1 if zero_based else total_pages
    
    if not isinstance(page_number, int):
        return Failure(ValidationError(
            message="Page number must be an integer",
            field_name="page_number",
            invalid_value=str(page_number),
        ))
    
    if page_number < min_page:
        return Failure(ValidationError(
            message=f"Page number must be at least {min_page}",
            field_name="page_number",
            invalid_value=str(page_number),
        ))
    
    if page_number > max_page:
        return Failure(ValidationError(
            message=f"Page number must be at most {max_page}",
            field_name="page_number",
            invalid_value=str(page_number),
        ))
    
    return Success(page_number)


def validate_zoom_level(
    zoom_level: float,
    min_zoom: float = 0.1,
    max_zoom: float = 5.0,
) -> Result[float]:
    """
    Validate a zoom level.
    
    Args:
        zoom_level: Zoom level to validate.
        min_zoom: Minimum allowed zoom.
        max_zoom: Maximum allowed zoom.
    
    Returns:
        Result containing the validated (and clamped) zoom level.
    """
    if not isinstance(zoom_level, (int, float)):
        return Failure(ValidationError(
            message="Zoom level must be a number",
            field_name="zoom_level",
            invalid_value=str(zoom_level),
        ))
    
    if zoom_level < min_zoom:
        return Success(min_zoom)
    
    if zoom_level > max_zoom:
        return Success(max_zoom)
    
    return Success(float(zoom_level))


def validate_rotation(rotation: int) -> Result[int]:
    """
    Validate and normalize a rotation value.
    
    Args:
        rotation: Rotation in degrees.
    
    Returns:
        Result containing normalized rotation (0, 90, 180, or 270).
    """
    if not isinstance(rotation, int):
        return Failure(ValidationError(
            message="Rotation must be an integer",
            field_name="rotation",
            invalid_value=str(rotation),
        ))
    
    normalized = rotation % 360
    
    valid_rotations = [0, 90, 180, 270]
    
    closest = min(valid_rotations, key=lambda x: abs(x - normalized))
    
    return Success(closest)


def validate_color_hex(color_hex: str) -> Result[str]:
    """
    Validate a hex color string.
    
    Args:
        color_hex: Color string to validate (with or without #).
    
    Returns:
        Result containing the validated color string (with #).
    """
    if not isinstance(color_hex, str):
        return Failure(ValidationError(
            message="Color must be a string",
            field_name="color",
            invalid_value=str(color_hex),
        ))
    
    color_hex = color_hex.strip()
    
    if color_hex.startswith("#"):
        color_hex = color_hex[1:]
    
    hex_pattern = re.compile(r'^[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$')
    
    if not hex_pattern.match(color_hex):
        return Failure(ValidationError(
            message="Invalid hex color format. Use #RRGGBB or #RRGGBBAA",
            field_name="color",
            invalid_value=color_hex,
        ))
    
    return Success(f"#{color_hex.lower()}")


def validate_annotation_bounds(
    bounds: Tuple[float, float, float, float],
    page_width: float,
    page_height: float,
) -> Result[Tuple[float, float, float, float]]:
    """
    Validate annotation bounding rectangle.
    
    Args:
        bounds: Rectangle as (x, y, width, height).
        page_width: Width of the page.
        page_height: Height of the page.
    
    Returns:
        Result containing validated bounds.
    """
    if len(bounds) != 4:
        return Failure(ValidationError(
            message="Bounds must have 4 values: x, y, width, height",
            field_name="bounds",
            invalid_value=str(bounds),
        ))
    
    x, y, width, height = bounds
    
    for i, value in enumerate([x, y, width, height]):
        if not isinstance(value, (int, float)):
            return Failure(ValidationError(
                message="All bounds values must be numbers",
                field_name="bounds",
                invalid_value=str(bounds),
            ))
    
    if width <= 0 or height <= 0:
        return Failure(ValidationError(
            message="Width and height must be positive",
            field_name="bounds",
            invalid_value=str(bounds),
        ))
    
    if x < 0:
        x = 0
    if y < 0:
        y = 0
    
    if x + width > page_width:
        width = page_width - x
    if y + height > page_height:
        height = page_height - y
    
    return Success((x, y, width, height))


def validate_percentage(
    value: float,
    field_name: str = "percentage",
    min_value: float = 0.0,
    max_value: float = 100.0,
) -> Result[float]:
    """
    Validate a percentage value.
    
    Args:
        value: Value to validate.
        field_name: Name of the field for error messages.
        min_value: Minimum allowed percentage.
        max_value: Maximum allowed percentage.
    
    Returns:
        Result containing validated percentage.
    """
    if not isinstance(value, (int, float)):
        return Failure(ValidationError(
            message=f"{field_name} must be a number",
            field_name=field_name,
            invalid_value=str(value),
        ))
    
    if value < min_value:
        return Failure(ValidationError(
            message=f"{field_name} must be at least {min_value}",
            field_name=field_name,
            invalid_value=str(value),
        ))
    
    if value > max_value:
        return Failure(ValidationError(
            message=f"{field_name} must be at most {max_value}",
            field_name=field_name,
            invalid_value=str(value),
        ))
    
    return Success(float(value))


def validate_string_length(
    value: str,
    field_name: str,
    min_length: int = 0,
    max_length: int = 1000,
    allow_empty: bool = True,
) -> Result[str]:
    """
    Validate string length.
    
    Args:
        value: String to validate.
        field_name: Name of the field for error messages.
        min_length: Minimum length.
        max_length: Maximum length.
        allow_empty: Whether empty strings are allowed.
    
    Returns:
        Result containing validated string.
    """
    if not isinstance(value, str):
        return Failure(ValidationError(
            message=f"{field_name} must be a string",
            field_name=field_name,
            invalid_value=str(type(value)),
        ))
    
    if not allow_empty and len(value.strip()) == 0:
        return Failure(ValidationError(
            message=f"{field_name} cannot be empty",
            field_name=field_name,
            invalid_value="",
        ))
    
    if len(value) < min_length:
        return Failure(ValidationError(
            message=f"{field_name} must be at least {min_length} characters",
            field_name=field_name,
            invalid_value=str(len(value)),
        ))
    
    if len(value) > max_length:
        return Failure(ValidationError(
            message=f"{field_name} must be at most {max_length} characters",
            field_name=field_name,
            invalid_value=str(len(value)),
        ))
    
    return Success(value)


def validate_positive_number(
    value: float,
    field_name: str,
    allow_zero: bool = True,
) -> Result[float]:
    """
    Validate that a number is positive.
    
    Args:
        value: Number to validate.
        field_name: Name of the field for error messages.
        allow_zero: Whether zero is allowed.
    
    Returns:
        Result containing validated number.
    """
    if not isinstance(value, (int, float)):
        return Failure(ValidationError(
            message=f"{field_name} must be a number",
            field_name=field_name,
            invalid_value=str(value),
        ))
    
    if allow_zero:
        if value < 0:
            return Failure(ValidationError(
                message=f"{field_name} must be non-negative",
                field_name=field_name,
                invalid_value=str(value),
            ))
    else:
        if value <= 0:
            return Failure(ValidationError(
                message=f"{field_name} must be positive",
                field_name=field_name,
                invalid_value=str(value),
            ))
    
    return Success(float(value))


def validate_in_list(
    value: str,
    allowed_values: list[str],
    field_name: str,
    case_sensitive: bool = True,
) -> Result[str]:
    """
    Validate that a value is in a list of allowed values.
    
    Args:
        value: Value to validate.
        allowed_values: List of allowed values.
        field_name: Name of the field for error messages.
        case_sensitive: Whether comparison is case sensitive.
    
    Returns:
        Result containing validated value.
    """
    if case_sensitive:
        if value not in allowed_values:
            return Failure(ValidationError(
                message=f"{field_name} must be one of: {', '.join(allowed_values)}",
                field_name=field_name,
                invalid_value=value,
            ))
        return Success(value)
    else:
        lower_value = value.lower()
        lower_allowed = {v.lower(): v for v in allowed_values}
        if lower_value not in lower_allowed:
            return Failure(ValidationError(
                message=f"{field_name} must be one of: {', '.join(allowed_values)}",
                field_name=field_name,
                invalid_value=value,
            ))
        return Success(lower_allowed[lower_value])
