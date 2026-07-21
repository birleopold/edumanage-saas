from unittest.mock import patch

from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from .observability import ObservabilityMiddleware, QueryCounter
from .request_ids import REQUEST_ID_HEADER, ensure_request_id


class RequestIdTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_valid_upstream_request_id_is_preserved(self):
        request = self.factory.get("/health/", HTTP_X_REQUEST_ID="proxy-abc_123:edge")

        request_id = ensure_request_id(request)

        self.assertEqual(request_id, "proxy-abc_123:edge")
        self.assertEqual(request.request_id, request_id)

    def test_invalid_upstream_request_id_is_replaced(self):
        request = self.factory.get("/health/", HTTP_X_REQUEST_ID="bad request id\nunsafe")

        request_id = ensure_request_id(request)

        self.assertRegex(request_id, r"^[a-f0-9]{32}$")
        self.assertNotIn("unsafe", request_id)

    def test_observability_adds_request_id_response_header(self):
        middleware = ObservabilityMiddleware(lambda request: HttpResponse("ok"))
        request = self.factory.get("/health/")

        response = middleware(request)

        self.assertEqual(response[REQUEST_ID_HEADER], request.request_id)

    def test_query_counter_wraps_and_counts_execution(self):
        counter = QueryCounter()
        calls = []

        def execute(sql, params, many, context):
            calls.append((sql, params, many, context))
            return "result"

        result = counter(execute, "SELECT 1", (), False, {"source": "test"})

        self.assertEqual(result, "result")
        self.assertEqual(counter.count, 1)
        self.assertEqual(calls[0][0], "SELECT 1")


class ProductionQueryCountTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(SLOW_QUERY_COUNT_THRESHOLD=1, SLOW_REQUEST_THRESHOLD_MS=999999)
    def test_query_warning_works_without_debug_query_log(self):
        def database_view(request):
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return HttpResponse("ok")

        middleware = ObservabilityMiddleware(database_view)
        request = self.factory.get("/reports/")

        with patch("apps.tenant.audit.observability.logger.warning") as warning:
            response = middleware(request)

        query_warnings = [
            call
            for call in warning.call_args_list
            if call.args and call.args[0] == "High query count request detected"
        ]
        self.assertEqual(response.status_code, 200)
        self.assertTrue(query_warnings)
        context = query_warnings[0].kwargs["extra"]["request_context"]
        self.assertGreaterEqual(context["query_count"], 1)
        self.assertEqual(context["request_id"], response[REQUEST_ID_HEADER])
