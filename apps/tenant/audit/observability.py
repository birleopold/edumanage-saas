import logging
import time

from django.conf import settings
from django.db import connection

from .request_ids import apply_request_id, ensure_request_id


logger = logging.getLogger("edumanage.observability")


class QueryCounter:
    """Count database executions even when Django's debug query log is off."""

    def __init__(self):
        self.count = 0

    def __call__(self, execute, sql, params, many, context):
        self.count += 1
        return execute(sql, params, many, context)


class ObservabilityMiddleware:
    """Log production diagnostics without surfacing stack traces to users."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ensure_request_id(request)
        started = time.monotonic()
        query_counter = QueryCounter()

        try:
            with connection.execute_wrapper(query_counter):
                response = self.get_response(request)
        except Exception:
            context = self._request_context(request)
            context.update(
                {
                    "duration_ms": int((time.monotonic() - started) * 1000),
                    "query_count": query_counter.count,
                }
            )
            logger.exception(
                "Unhandled request exception",
                extra={"request_context": context},
            )
            raise

        elapsed_ms = int((time.monotonic() - started) * 1000)
        context = self._request_context(request)
        context.update(
            {
                "status_code": getattr(response, "status_code", None),
                "duration_ms": elapsed_ms,
                "query_count": query_counter.count,
            }
        )

        if elapsed_ms >= getattr(settings, "SLOW_REQUEST_THRESHOLD_MS", 1500):
            logger.warning("Slow request detected", extra={"request_context": context})
        if query_counter.count >= getattr(settings, "SLOW_QUERY_COUNT_THRESHOLD", 75):
            logger.warning("High query count request detected", extra={"request_context": context})

        return apply_request_id(response, request)

    def _request_context(self, request):
        user = getattr(request, "user", None)
        tenant = getattr(request, "tenant", None)
        return {
            "request_id": ensure_request_id(request),
            "method": getattr(request, "method", ""),
            "path": getattr(request, "path", ""),
            "user_id": getattr(user, "pk", None) if getattr(user, "is_authenticated", False) else None,
            "tenant": getattr(tenant, "schema_name", None) or getattr(tenant, "name", None),
            "remote_addr": request.META.get("REMOTE_ADDR") if hasattr(request, "META") else None,
        }
