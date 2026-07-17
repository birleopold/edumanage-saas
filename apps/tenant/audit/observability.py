import logging
import time

from django.conf import settings
from django.db import connection


logger = logging.getLogger("edumanage.observability")


class ObservabilityMiddleware:
    """Log production diagnostics without surfacing stack traces to users."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.monotonic()
        starting_query_count = len(connection.queries)
        try:
            response = self.get_response(request)
        except Exception:
            logger.exception(
                "Unhandled request exception",
                extra={"request_context": self._request_context(request)},
            )
            raise

        elapsed_ms = int((time.monotonic() - started) * 1000)
        query_count = max(len(connection.queries) - starting_query_count, 0)
        context = self._request_context(request)
        context.update(
            {
                "status_code": getattr(response, "status_code", None),
                "duration_ms": elapsed_ms,
                "query_count": query_count,
            }
        )

        if elapsed_ms >= getattr(settings, "SLOW_REQUEST_THRESHOLD_MS", 1500):
            logger.warning("Slow request detected", extra={"request_context": context})
        if query_count >= getattr(settings, "SLOW_QUERY_COUNT_THRESHOLD", 75):
            logger.warning("High query count request detected", extra={"request_context": context})

        return response

    def _request_context(self, request):
        user = getattr(request, "user", None)
        tenant = getattr(request, "tenant", None)
        return {
            "method": getattr(request, "method", ""),
            "path": getattr(request, "path", ""),
            "user_id": getattr(user, "pk", None) if getattr(user, "is_authenticated", False) else None,
            "tenant": getattr(tenant, "schema_name", None) or getattr(tenant, "name", None),
            "remote_addr": request.META.get("REMOTE_ADDR") if hasattr(request, "META") else None,
        }
