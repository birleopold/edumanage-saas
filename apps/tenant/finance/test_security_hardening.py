import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import RequestFactory, SimpleTestCase, override_settings

from .payment_callback_views import mtn_momo_callback
from .webhook_security import install_webhook_delivery_guard, validate_webhook_target


class PaymentCallbackFailClosedTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(PAYMENT_CALLBACKS_ENABLED=False, MTN_MOMO_CALLBACK_SECRET="secret")
    def test_disabled_callbacks_return_service_unavailable(self):
        request = self.factory.post("/callback/", data={"reference": "ref-1"})
        response = mtn_momo_callback(request)
        self.assertEqual(response.status_code, 503)

    @override_settings(PAYMENT_CALLBACKS_ENABLED=True, MTN_MOMO_CALLBACK_SECRET="")
    def test_missing_secret_is_rejected(self):
        request = self.factory.post("/callback/", data={"reference": "ref-1"})
        response = mtn_momo_callback(request)
        self.assertEqual(response.status_code, 503)

    @override_settings(PAYMENT_CALLBACKS_ENABLED=True, MTN_MOMO_CALLBACK_SECRET="supersecret")
    @patch("apps.tenant.finance.payment_callback_views.process_gateway_callback")
    def test_valid_hmac_signature_is_accepted(self, process_callback):
        payload = {"reference": "ref-1", "status": "SUCCESSFUL", "amount": "50000", "currency": "UGX"}
        raw = json.dumps(payload).encode("utf-8")
        signature = hmac.new(b"supersecret", raw, hashlib.sha256).hexdigest()
        process_callback.return_value = SimpleNamespace(processed=True, id=7, error_message="")
        request = self.factory.post(
            "/callback/",
            data=raw,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE_256=f"sha256={signature}",
        )
        response = mtn_momo_callback(request)
        self.assertEqual(response.status_code, 200)
        process_callback.assert_called_once()


class WebhookTargetValidationTests(SimpleTestCase):
    @override_settings(WEBHOOK_ALLOW_PRIVATE_TARGETS=False, WEBHOOK_ALLOW_HTTP=False, WEBHOOK_ALLOWED_HOSTS=())
    def test_loopback_target_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_webhook_target("https://127.0.0.1:9000/private")

    @override_settings(WEBHOOK_ALLOW_PRIVATE_TARGETS=False, WEBHOOK_ALLOW_HTTP=False, WEBHOOK_ALLOWED_HOSTS=())
    def test_http_target_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_webhook_target("http://example.com/webhook")


class WebhookDeliveryGuardTests(SimpleTestCase):
    @override_settings(WEBHOOK_ALLOW_PRIVATE_TARGETS=False, WEBHOOK_ALLOW_HTTP=False, WEBHOOK_ALLOWED_HOSTS=())
    def test_delivery_revalidates_a_target_that_changed_after_save(self):
        from . import services

        install_webhook_delivery_guard()
        endpoint = SimpleNamespace(target_url="https://127.0.0.1/private", secret="")
        result = services._deliver_webhook(endpoint, "message_log.created", {"event": "test"})

        self.assertFalse(result["success"])
        self.assertIn("blocked_webhook_target", result["error_message"])
