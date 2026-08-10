from __future__ import annotations

import re
from numbers import Number

from django.core.exceptions import ValidationError

ALLOWED_ELEMENT_TYPES = {"text", "field", "image", "qr", "rectangle", "line", "results_table"}
ALLOWED_FONTS = {"Helvetica", "Times-Roman", "Courier"}
ALLOWED_BINDINGS = {
    "school.name", "school.logo", "school.email", "school.phone", "school.address",
    "campus.name", "campus.code", "campus.logo", "campus.email", "campus.phone", "campus.address",
    "student.full_name", "student.first_name", "student.last_name", "student.student_id", "student.learner_id",
    "student.email", "student.date_of_birth", "student.class", "student.stream", "student.photo",
    "academic.term", "academic.year", "academic.mean", "academic.overall_grade", "academic.overall_remark",
    "document.reference", "document.issue_date", "document.verification_url",
}
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _number(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Number):
        raise ValidationError(f"{label} must be a number.")
    return float(value)


def validate_design_document(document: dict, page_width_mm: float, page_height_mm: float) -> None:
    if not isinstance(document, dict):
        raise ValidationError("Design data must be a JSON object.")
    pages = document.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValidationError("A design must contain at least one page.")
    if len(pages) > 8:
        raise ValidationError("A design may contain at most 8 pages.")
    seen = set()
    total_elements = 0
    for page_index, page in enumerate(pages, start=1):
        if not isinstance(page, dict):
            raise ValidationError(f"Page {page_index} must be an object.")
        elements = page.get("elements", [])
        if not isinstance(elements, list):
            raise ValidationError(f"Page {page_index} elements must be a list.")
        total_elements += len(elements)
        if total_elements > 300:
            raise ValidationError("A design may contain at most 300 elements.")
        for element in elements:
            if not isinstance(element, dict):
                raise ValidationError("Every design element must be an object.")
            element_id = str(element.get("id") or "").strip()
            if not element_id or element_id in seen:
                raise ValidationError("Every design element must have a unique id.")
            if len(element_id) > 120:
                raise ValidationError("Design element ids must be 120 characters or fewer.")
            seen.add(element_id)
            element_type = element.get("type")
            if element_type not in ALLOWED_ELEMENT_TYPES:
                raise ValidationError(f"Unsupported element type: {element_type!r}.")
            x = _number(element.get("x", 0), "x")
            y = _number(element.get("y", 0), "y")
            width = _number(element.get("width", 1), "width")
            height = _number(element.get("height", 1), "height")
            if min(x, y, width, height) < 0 or width == 0 or height == 0:
                raise ValidationError("Element positions and dimensions must be positive.")
            if x + width > page_width_mm + 0.05 or y + height > page_height_mm + 0.05:
                raise ValidationError(f"Element {element_id!r} extends beyond the page boundary.")
            binding = element.get("binding")
            if binding and binding not in ALLOWED_BINDINGS:
                raise ValidationError(f"Unsupported data binding: {binding!r}.")
            font = element.get("fontFamily", "Helvetica")
            if font not in ALLOWED_FONTS:
                raise ValidationError(f"Unsupported font family: {font!r}.")
            if len(str(element.get("text", ""))) > 5000:
                raise ValidationError("Static text elements may contain at most 5000 characters.")
            for key in ("prefix", "suffix"):
                if len(str(element.get(key, ""))) > 250:
                    raise ValidationError(f"Element {key} may contain at most 250 characters.")
            for key in ("color", "backgroundColor", "borderColor"):
                color = element.get(key)
                if color and color != "transparent" and not HEX_COLOR.match(str(color)):
                    raise ValidationError(f"Invalid {key} value.")
