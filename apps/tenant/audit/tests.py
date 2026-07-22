from unittest import mock

from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from .observability import ObservabilityMiddleware


class ObservabilityMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_unhandled_exception_is_logged_with_request_context(self):
        request = self.factory.get("/boom/", REMOTE_ADDR="127.0.0.1")

        def explode(_request):
            raise RuntimeError("kaboom")

        with self.assertLogs("edumanage.observability", level="ERROR") as logs:
            with self.assertRaises(RuntimeError):
                ObservabilityMiddleware(explode)(request)

        self.assertIn("Unhandled request exception", "\n".join(logs.output))

    @override_settings(SLOW_REQUEST_THRESHOLD_MS=1, SLOW_QUERY_COUNT_THRESHOLD=999)
    def test_slow_request_is_logged(self):
        request = self.factory.get("/slow/")

        def respond(_request):
            return HttpResponse("ok")

        with mock.patch(
            "apps.tenant.audit.observability.time.monotonic",
            side_effect=[1.0, 1.2],
        ):
            with self.assertLogs("edumanage.observability", level="WARNING") as logs:
                response = ObservabilityMiddleware(respond)(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Slow request detected", "\n".join(logs.output))

    @override_settings(SLOW_REQUEST_THRESHOLD_MS=999999, SLOW_QUERY_COUNT_THRESHOLD=1)
    def test_high_query_count_is_logged(self):
        request = self.factory.get("/query-heavy/")

        def respond(_request):
            # Use an actual database execution because production query counting
            # is implemented with Django's execution wrapper, not DEBUG-only
            # connection.queries bookkeeping.
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return HttpResponse("ok")

        with self.assertLogs("edumanage.observability", level="WARNING") as logs:
            response = ObservabilityMiddleware(respond)(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("High query count request detected", "\n".join(logs.output))
