"""Request correlation helpers shared by middleware and error pages."""

from __future__ import annotations

import re
import uuid


REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _valid_request_id(value: object) -> str:
    candidate = str(value or "").strip()
    if _REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return ""


def ensure_request_id(request) -> str:
    """Return a safe correlation ID and attach it to the request.

    A valid reverse-proxy supplied ``X-Request-ID`` is preserved so application
    logs can be correlated with Nginx, load-balancer and monitoring records.
    Invalid, blank or overlong values are replaced rather than reflected.
    """

    current = _valid_request_id(getattr(request, "request_id", ""))
    if current:
        return current

    meta = getattr(request, "META", {}) or {}
    incoming = _valid_request_id(meta.get("HTTP_X_REQUEST_ID", ""))
    request_id = incoming or uuid.uuid4().hex
    request.request_id = request_id
    return request_id


def apply_request_id(response, request):
    """Attach the correlation ID to an HTTP response."""

    response[REQUEST_ID_HEADER] = ensure_request_id(request)
    return response
