from decimal import Decimal
import hashlib
import hmac
import json

from django.test import Client
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.tenant.announcements.models import Announcement
from apps.tenant.finance.models import (
    CommunicationTemplate,
    IntegrationApiKey,
    IntegrationApiKeyScope,
    IntegrationScope,
    IntegrationEventLog,
    Invoice,
    MobilePaymentRequest,
    OutboundMessageLog,
    Payment,
    PaymentGatewayEvent,
    InboundWebhookEvent,
    WebhookDelivery,
    WebhookEndpoint,
    WebhookRetryQueueItem,
)
from apps.tenant.finance.services import (
    build_fee_reminder_message,
    send_urgent_announcement_broadcast,
    messaging_readiness_snapshot,
    build_payment_receipt_message,
    normalize_phone_for_whatsapp,
    retry_outbound_message_log_by_id,
    retry_outbound_message_logs,
    process_webhook_retry_queue,
    send_payment_receipt_for_payment,
    send_fee_reminder_for_invoice,
)
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role, User, UserRole


class FinanceReminderPhaseOneTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.student = StudentProfile.objects.create(
            first_name="Amina",
            last_name="Nabirye",
            student_id="ST-001",
        )
        self.invoice = Invoice.objects.create(
            student=self.student,
            reference="INV-001",
            opening_balance=Decimal("150000"),
        )

    def test_normalize_phone_for_whatsapp_local_number(self):
        normalized = normalize_phone_for_whatsapp("0772 123 456")
        self.assertEqual(normalized, "256772123456")

    def test_normalize_phone_for_whatsapp_international_number(self):
        normalized = normalize_phone_for_whatsapp("+256 772 123 456")
        self.assertEqual(normalized, "256772123456")

    @override_settings(
        FEE_REMINDER_CHANNEL="WHATSAPP",
        FEE_REMINDER_DEFAULT_COUNTRY_CODE="256",
    )
    def test_send_fee_reminder_uses_handler_and_normalized_phone(self):
        captured = {}

        def fake_handler(phone: str, message: str, channel: str = "SMS") -> bool:
            captured["phone"] = phone
            captured["message"] = message
            captured["channel"] = channel
            return True

        with override_settings(FEE_REMINDER_HANDLER=fake_handler):
            parent = ParentProfile.objects.create(
                first_name="Grace",
                last_name="Nakanwagi",
                phone="0772 123 456",
            )
            ParentStudentLink.objects.create(parent=parent, student=self.student, is_primary=True)
            result = send_fee_reminder_for_invoice(
                self.invoice,
                currency_code="UGX",
                school_name="EduManage",
            )

        self.assertEqual(result[0]["status"], "sent")
        self.assertEqual(captured["phone"], "256772123456")
        self.assertEqual(captured["channel"], "WHATSAPP")
        self.assertIn("Fee reminder", captured["message"])
        self.assertIn("INV-001", captured["message"])
        self.assertEqual(
            OutboundMessageLog.objects.filter(message_type="FEE_REMINDER", status="SENT").count(),
            1,
        )

    def test_send_fee_reminder_returns_no_phone(self):
        result = send_fee_reminder_for_invoice(self.invoice)
        self.assertEqual(result, [{"phone": "", "status": "no_phone", "channel": "SMS"}])

    @override_settings(FEE_REMINDER_PORTAL_BASE_URL="https://school.example.com")
    def test_build_fee_reminder_message_includes_portal_link(self):
        msg = build_fee_reminder_message(
            self.invoice,
            currency_code="UGX",
            school_name="EduManage",
        )
        self.assertIn("https://school.example.com/parent/finance/invoices/", msg)

    @override_settings(
        FEE_REMINDER_CHANNEL="WHATSAPP",
        FEE_REMINDER_DEFAULT_COUNTRY_CODE="256",
        FEE_REMINDER_PORTAL_BASE_URL="https://school.example.com",
    )
    def test_send_payment_receipt_dispatch_and_logs(self):
        captured = {}

        def fake_handler(phone: str, message: str, channel: str = "SMS") -> bool:
            captured["phone"] = phone
            captured["message"] = message
            captured["channel"] = channel
            return True

        with override_settings(FEE_REMINDER_HANDLER=fake_handler):
            parent = ParentProfile.objects.create(
                first_name="Judith",
                last_name="Achen",
                phone="0772 123 456",
            )
            ParentStudentLink.objects.create(parent=parent, student=self.student, is_primary=True)
            payment = Payment.objects.create(
                invoice=self.invoice,
                amount=Decimal("50000"),
                method=Payment.MOBILE,
                mobile_network=Payment.MTN_MOMO,
            )
            result = send_payment_receipt_for_payment(
                payment,
                currency_code="UGX",
                school_name="EduManage",
            )

        self.assertEqual(result[0]["status"], "sent")
        self.assertEqual(captured["phone"], "256772123456")
        self.assertEqual(captured["channel"], "WHATSAPP")
        self.assertIn("/parent/finance/invoices/", captured["message"])
        self.assertEqual(
            OutboundMessageLog.objects.filter(message_type="PAYMENT_RECEIPT", status="SENT").count(),
            1,
        )

    @override_settings(FEE_REMINDER_PORTAL_BASE_URL="https://school.example.com")
    def test_build_payment_receipt_message_includes_receipt_link(self):
        payment = Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal("20000"),
            method=Payment.CASH,
        )
        msg = build_payment_receipt_message(
            payment,
            currency_code="UGX",
            school_name="EduManage",
        )
        self.assertIn("/parent/finance/invoices/", msg)
        self.assertIn("/payments/", msg)

    def test_custom_communication_template_overrides_fee_message(self):
        CommunicationTemplate.objects.filter(message_type=OutboundMessageLog.FEE_REMINDER).update(
            is_active=False
        )
        CommunicationTemplate.objects.create(
            code="test_override_fee_msg",
            name="Test fee override",
            message_type=OutboundMessageLog.FEE_REMINDER,
            body="CUSTOMTEMPLATE {{student_name}} {{amount}} {{parent_name}}",
            sort_order=0,
        )
        parent = ParentProfile.objects.create(first_name="Pat", last_name="One", phone="123456")
        ParentStudentLink.objects.create(parent=parent, student=self.student, is_primary=True)
        msg = build_fee_reminder_message(
            self.invoice,
            currency_code="UGX",
            school_name="Sch",
            parent=parent,
        )
        self.assertIn("CUSTOMTEMPLATE", msg)
        self.assertIn("Amina", msg)
        self.assertIn("Pat", msg)

    def test_messaging_readiness_snapshot_includes_expected_keys(self):
        snap = messaging_readiness_snapshot(sample_limit=10)
        self.assertIn("channel", snap)
        self.assertIn("handler_resolved", snap)
        self.assertIn("failed_logs_count", snap)
        self.assertGreaterEqual(snap["invoice_sample_size"], 1)

    @override_settings(FEE_REMINDER_CHANNEL="WHATSAPP", FEE_REMINDER_DEFAULT_COUNTRY_CODE="256")
    def test_retry_outbound_message_logs_retries_failed_entry(self):
        captured = {}

        def fake_handler(phone: str, message: str, channel: str = "SMS") -> bool:
            captured["phone"] = phone
            captured["channel"] = channel
            return True

        with override_settings(FEE_REMINDER_HANDLER=fake_handler):
            failed = OutboundMessageLog.objects.create(
                message_type=OutboundMessageLog.FEE_REMINDER,
                channel=OutboundMessageLog.WHATSAPP,
                invoice=self.invoice,
                phone_raw="0772 123 456",
                status=OutboundMessageLog.FAILED,
                message="Test reminder",
                error_message="previous failure",
            )
            summary = retry_outbound_message_logs(limit=10)

        self.assertEqual(summary["processed"], 1)
        self.assertEqual(summary["sent"], 1)
        self.assertEqual(captured["phone"], "256772123456")
        self.assertEqual(captured["channel"], "WHATSAPP")
        self.assertEqual(
            OutboundMessageLog.objects.filter(provider_response__retry_of_log_id=failed.pk).count(),
            1,
        )

    @override_settings(FEE_REMINDER_CHANNEL="SMS")
    def test_retry_outbound_message_log_by_id_dry_run_creates_retry_log(self):
        original = OutboundMessageLog.objects.create(
            message_type=OutboundMessageLog.FEE_REMINDER,
            channel=OutboundMessageLog.SMS,
            invoice=self.invoice,
            phone_raw="0772123456",
            status=OutboundMessageLog.FAILED,
            message="test message",
            error_message="network issue",
        )
        result = retry_outbound_message_log_by_id(original.pk, dry_run=True)
        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(
            OutboundMessageLog.objects.filter(provider_response__retry_of_log_id=original.pk, status="DRY_RUN").count(),
            1,
        )

    @override_settings(FEE_REMINDER_CHANNEL="WHATSAPP", FEE_REMINDER_DEFAULT_COUNTRY_CODE="256")
    def test_parent_whatsapp_consent_blocks_fee_reminder_delivery(self):
        parent = ParentProfile.objects.create(
            first_name="No",
            last_name="Consent",
            phone="0772 123 456",
            allow_whatsapp_alerts=False,
        )
        ParentStudentLink.objects.create(parent=parent, student=self.student, is_primary=True)
        result = send_fee_reminder_for_invoice(self.invoice)
        self.assertEqual(result[0]["status"], "no_phone")

    @override_settings(FEE_REMINDER_CHANNEL="WHATSAPP", FEE_REMINDER_DEFAULT_COUNTRY_CODE="256")
    def test_urgent_announcement_broadcast_respects_parent_consent(self):
        captured = {"sent": 0}

        def fake_handler(phone: str, message: str, channel: str = "SMS") -> bool:
            captured["sent"] += 1
            return True

        with override_settings(FEE_REMINDER_HANDLER=fake_handler):
            allowed = ParentProfile.objects.create(
                first_name="Allowed",
                last_name="Parent",
                phone="0772 000 001",
                allow_whatsapp_alerts=True,
            )
            blocked = ParentProfile.objects.create(
                first_name="Blocked",
                last_name="Parent",
                phone="0772 000 002",
                allow_whatsapp_alerts=False,
            )
            ParentStudentLink.objects.create(parent=allowed, student=self.student, is_primary=True)
            ParentStudentLink.objects.create(parent=blocked, student=self.student)
            ann = Announcement.objects.create(
                title="Urgent Closure",
                body="School closes early today.",
                audience=Announcement.PARENTS,
                is_active=True,
                is_urgent=True,
            )
            summary = send_urgent_announcement_broadcast(ann, school_name="EduManage")

        self.assertEqual(captured["sent"], 1)
        self.assertEqual(summary["sent"], 1)
        self.assertEqual(
            OutboundMessageLog.objects.filter(message_type="URGENT_ANNOUNCEMENT", status="SENT").count(),
            1,
        )

    def test_integration_api_key_auth_for_message_logs_endpoint(self):
        key_obj, raw_key = IntegrationApiKey.create_with_plaintext("Test Key")
        self.assertTrue(key_obj.is_active)
        self.assertIsNone(key_obj.last_used_at)
        response = self.client.get(
            "/api/v1/integrations/message-logs/",
            HTTP_X_API_KEY=raw_key,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("results", payload)
        key_obj.refresh_from_db()
        self.assertIsNotNone(key_obj.last_used_at)

    def test_scoped_integration_key_denies_wrong_scope_without_marking_used(self):
        key_obj, raw_key = IntegrationApiKey.create_with_plaintext("Attendance Only")
        attendance_scope = IntegrationScope.objects.get(code="attendance-write")
        IntegrationApiKeyScope.objects.create(api_key=key_obj, scope=attendance_scope)

        response = self.client.get(
            "/api/v1/integrations/ready/",
            HTTP_X_API_KEY=raw_key,
        )

        self.assertEqual(response.status_code, 403)
        key_obj.refresh_from_db()
        self.assertIsNone(key_obj.last_used_at)

    def test_scoped_integration_key_marks_used_after_scope_passes(self):
        key_obj, raw_key = IntegrationApiKey.create_with_plaintext("Integration Admin")
        admin_scope = IntegrationScope.objects.get(code="integrations-admin")
        IntegrationApiKeyScope.objects.create(api_key=key_obj, scope=admin_scope)

        response = self.client.get(
            "/api/v1/integrations/ready/",
            HTTP_X_API_KEY=raw_key,
        )

        self.assertEqual(response.status_code, 200)
        key_obj.refresh_from_db()
        self.assertIsNotNone(key_obj.last_used_at)

    def test_api_key_rotation_disables_old_key_and_preserves_scopes(self):
        admin_user = User.objects.create_superuser(
            username="integration_key_admin",
            email="integration-key-admin@example.com",
            password="test-pass-123",
        )
        self.client.login(username="integration_key_admin", password="test-pass-123")
        old_key, _ = IntegrationApiKey.create_with_plaintext("Rotating Key")
        admin_scope = IntegrationScope.objects.get(code="integrations-admin")
        gps_scope = IntegrationScope.objects.get(code="transport-gps")
        IntegrationApiKeyScope.objects.create(api_key=old_key, scope=admin_scope)
        IntegrationApiKeyScope.objects.create(api_key=old_key, scope=gps_scope)

        response = self.client.post(reverse("admin_connectors_api_key_rotate", kwargs={"pk": old_key.pk}))

        self.assertEqual(response.status_code, 302)
        old_key.refresh_from_db()
        self.assertFalse(old_key.is_active)
        new_key = IntegrationApiKey.objects.exclude(pk=old_key.pk).get(name="Rotating Key rotated")
        self.assertTrue(new_key.is_active)
        self.assertIsNone(new_key.last_used_at)
        self.assertEqual(
            set(new_key.scope_links.values_list("scope__code", flat=True)),
            {"integrations-admin", "transport-gps"},
        )

    @override_settings(
        FEE_REMINDER_CHANNEL="SMS",
        FEE_REMINDER_HANDLER="apps.tenant.finance.sms_defaults.log_fee_reminder_to_logger",
    )
    def test_webhook_delivery_record_created_for_message_log_event(self):
        WebhookEndpoint.objects.create(
            name="Failing endpoint",
            target_url="https://127.0.0.1:1/unreachable",
            secret="abc123",
            event_type=WebhookEndpoint.EVENT_MESSAGE_LOG_CREATED,
            is_active=True,
        )
        parent = ParentProfile.objects.create(
            first_name="Webhook",
            last_name="Parent",
            phone="0700000001",
            allow_sms_alerts=True,
        )
        ParentStudentLink.objects.create(parent=parent, student=self.student, is_primary=True)
        send_fee_reminder_for_invoice(self.invoice)
        self.assertGreaterEqual(WebhookDelivery.objects.count(), 1)
        self.assertGreaterEqual(WebhookRetryQueueItem.objects.count(), 1)

    def test_process_webhook_retry_queue_dry_run(self):
        endpoint = WebhookEndpoint.objects.create(
            name="Retry endpoint",
            target_url="https://127.0.0.1:1/unreachable",
            event_type=WebhookEndpoint.EVENT_MESSAGE_LOG_CREATED,
            is_active=True,
        )
        item = WebhookRetryQueueItem.objects.create(
            endpoint=endpoint,
            event_type=WebhookEndpoint.EVENT_MESSAGE_LOG_CREATED,
            payload={"event": "message_log.created"},
            is_active=True,
        )
        summary = process_webhook_retry_queue(limit=10, dry_run=True)
        self.assertEqual(summary["processed"], 1)
        item.refresh_from_db()
        self.assertTrue(item.is_active)

    @override_settings(WEBHOOK_MAX_RETRY_ATTEMPTS=2, WEBHOOK_RETRY_BASE_SECONDS=1)
    def test_process_webhook_retry_queue_caps_attempts_and_audits_terminal_failure(self):
        endpoint = WebhookEndpoint.objects.create(
            name="Terminal retry endpoint",
            target_url="https://127.0.0.1:1/unreachable",
            event_type=WebhookEndpoint.EVENT_MESSAGE_LOG_CREATED,
            is_active=True,
        )
        item = WebhookRetryQueueItem.objects.create(
            endpoint=endpoint,
            event_type=WebhookEndpoint.EVENT_MESSAGE_LOG_CREATED,
            payload={"event": "message_log.created"},
            attempt_count=1,
            max_attempts=99,
            is_active=True,
        )

        summary = process_webhook_retry_queue(limit=10)

        self.assertEqual(summary["processed"], 1)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["deactivated"], 1)
        item.refresh_from_db()
        self.assertFalse(item.is_active)
        self.assertEqual(item.attempt_count, 2)
        self.assertEqual(item.max_attempts, 2)
        self.assertTrue(WebhookDelivery.objects.filter(endpoint=endpoint, success=False).exists())
        self.assertTrue(
            IntegrationEventLog.objects.filter(
                event_type="webhook.retry.terminal",
                status=IntegrationEventLog.FAILED,
                external_reference=str(item.pk),
            ).exists()
        )

    def test_webhook_deliveries_api_includes_retry_failure_summary(self):
        key_obj, raw_key = IntegrationApiKey.create_with_plaintext("Webhook Dashboard")
        endpoint = WebhookEndpoint.objects.create(
            name="Dashboard endpoint",
            target_url="https://127.0.0.1:1/unreachable",
            event_type=WebhookEndpoint.EVENT_MESSAGE_LOG_CREATED,
            is_active=True,
        )
        WebhookDelivery.objects.create(
            endpoint=endpoint,
            event_type=WebhookEndpoint.EVENT_MESSAGE_LOG_CREATED,
            payload={"event": "message_log.created"},
            success=False,
            error_message="failed",
        )
        WebhookRetryQueueItem.objects.create(
            endpoint=endpoint,
            event_type=WebhookEndpoint.EVENT_MESSAGE_LOG_CREATED,
            payload={"event": "message_log.created"},
            is_active=True,
        )
        WebhookRetryQueueItem.objects.create(
            endpoint=endpoint,
            event_type=WebhookEndpoint.EVENT_MESSAGE_LOG_CREATED,
            payload={"event": "message_log.created"},
            attempt_count=5,
            is_active=False,
        )

        response = self.client.get(
            "/api/v1/integrations/webhook-deliveries/",
            HTTP_X_API_KEY=raw_key,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["failed_delivery_count"], 1)
        self.assertEqual(payload["active_retry_count"], 1)
        self.assertEqual(payload["terminal_retry_count"], 1)
        key_obj.refresh_from_db()
        self.assertIsNotNone(key_obj.last_used_at)

    @override_settings(WHATSAPP_STATUS_WEBHOOK_SECRET="supersecret")
    def test_whatsapp_status_callback_updates_delivery_status(self):
        log = OutboundMessageLog.objects.create(
            message_type=OutboundMessageLog.FEE_REMINDER,
            channel=OutboundMessageLog.WHATSAPP,
            status=OutboundMessageLog.SENT,
            provider_message_id="wamid.test123",
            message="test",
        )
        payload = {
            "entry": [
                {
                    "changes": [
                        {"value": {"statuses": [{"id": "wamid.test123", "status": "delivered"}]}}
                    ]
                }
            ]
        }
        raw = json.dumps(payload).encode("utf-8")
        sig = hmac.new(b"supersecret", raw, hashlib.sha256).hexdigest()
        response = self.client.post(
            "/api/v1/integrations/callbacks/whatsapp-status/",
            data=raw,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE_256=sig,
        )
        self.assertEqual(response.status_code, 200)
        log.refresh_from_db()
        self.assertEqual(log.provider_delivery_status, "delivered")
        self.assertEqual(InboundWebhookEvent.objects.filter(signature_valid=True).count(), 1)

    @override_settings(WHATSAPP_STATUS_WEBHOOK_SECRET="supersecret")
    def test_whatsapp_status_callback_rejects_bad_signature(self):
        payload = {"entry": []}
        raw = json.dumps(payload).encode("utf-8")
        response = self.client.post(
            "/api/v1/integrations/callbacks/whatsapp-status/",
            data=raw,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE_256="bad",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(InboundWebhookEvent.objects.filter(signature_valid=False).count(), 1)

    @override_settings(
        MTN_MOMO_CALLBACK_SECRET="supersecret",
        FEE_REMINDER_HANDLER="apps.tenant.finance.sms_defaults.log_fee_reminder_to_logger",
    )
    def test_payment_callback_rejects_missing_signature(self):
        payment_request = MobilePaymentRequest.objects.create(
            invoice=self.invoice,
            amount=Decimal("50000"),
            phone_number="0772123456",
            network=Payment.MTN_MOMO,
            provider_reference="mtn-ref-001",
            status=MobilePaymentRequest.PROCESSING,
        )

        response = self.client.post(
            reverse("finance_mtn_collection_update"),
            data={"reference": "mtn-ref-001", "status": "SUCCESSFUL"},
        )

        self.assertEqual(response.status_code, 401)
        payment_request.refresh_from_db()
        self.assertEqual(payment_request.status, MobilePaymentRequest.PROCESSING)
        self.assertFalse(PaymentGatewayEvent.objects.exists())
        self.assertFalse(Payment.objects.exists())

    @override_settings(
        MTN_MOMO_CALLBACK_SECRET="supersecret",
        FEE_REMINDER_HANDLER="apps.tenant.finance.sms_defaults.log_fee_reminder_to_logger",
    )
    def test_payment_callback_accepts_valid_hmac_signature(self):
        payment_request = MobilePaymentRequest.objects.create(
            invoice=self.invoice,
            amount=Decimal("50000"),
            phone_number="0772123456",
            network=Payment.MTN_MOMO,
            provider_reference="mtn-ref-002",
            status=MobilePaymentRequest.PROCESSING,
        )
        payload = {"reference": "mtn-ref-002", "status": "SUCCESSFUL"}
        raw = json.dumps(payload).encode("utf-8")
        sig = hmac.new(b"supersecret", raw, hashlib.sha256).hexdigest()

        response = self.client.post(
            reverse("finance_mtn_collection_update"),
            data=raw,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE_256=f"sha256={sig}",
        )

        self.assertEqual(response.status_code, 200)
        payment_request.refresh_from_db()
        self.assertEqual(payment_request.status, MobilePaymentRequest.SUCCESSFUL)
        self.assertEqual(PaymentGatewayEvent.objects.filter(processed=True).count(), 1)
        self.assertEqual(Payment.objects.filter(reference="mtn-ref-002").count(), 1)

    @override_settings(
        MTN_MOMO_CALLBACK_SECRET="supersecret",
        FEE_REMINDER_HANDLER="apps.tenant.finance.sms_defaults.log_fee_reminder_to_logger",
    )
    def test_payment_callback_replay_does_not_create_duplicate_payment(self):
        payment_request = MobilePaymentRequest.objects.create(
            invoice=self.invoice,
            amount=Decimal("50000"),
            phone_number="0772123456",
            network=Payment.MTN_MOMO,
            provider_reference="mtn-ref-003",
            status=MobilePaymentRequest.PROCESSING,
        )
        payload = {"reference": "mtn-ref-003", "status": "SUCCESSFUL"}
        raw = json.dumps(payload).encode("utf-8")
        sig = hmac.new(b"supersecret", raw, hashlib.sha256).hexdigest()

        first_response = self.client.post(
            reverse("finance_mtn_collection_update"),
            data=raw,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE_256=sig,
        )
        replay_response = self.client.post(
            reverse("finance_mtn_collection_update"),
            data=raw,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE_256=sig,
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(replay_response.status_code, 200)
        payment_request.refresh_from_db()
        self.assertEqual(payment_request.status, MobilePaymentRequest.SUCCESSFUL)
        self.assertEqual(Payment.objects.filter(reference="mtn-ref-003").count(), 1)
        self.assertEqual(PaymentGatewayEvent.objects.filter(provider_reference="mtn-ref-003").count(), 2)
        self.assertTrue(
            PaymentGatewayEvent.objects.filter(
                provider_reference="mtn-ref-003",
                error_message="Replay callback ignored.",
                processed=True,
            ).exists()
        )

    @override_settings(
        MTN_MOMO_CALLBACK_SECRET="supersecret",
        FEE_REMINDER_HANDLER="apps.tenant.finance.sms_defaults.log_fee_reminder_to_logger",
    )
    def test_completed_payment_callback_cannot_be_downgraded(self):
        payment = Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal("50000"),
            method=Payment.MOBILE,
            mobile_network=Payment.MTN_MOMO,
            reference="mtn-ref-004",
        )
        payment_request = MobilePaymentRequest.objects.create(
            invoice=self.invoice,
            amount=Decimal("50000"),
            phone_number="0772123456",
            network=Payment.MTN_MOMO,
            provider_reference="mtn-ref-004",
            status=MobilePaymentRequest.SUCCESSFUL,
            created_payment=payment,
        )

        response = self.client.post(
            reverse("finance_mtn_collection_update"),
            data={"reference": "mtn-ref-004", "status": "FAILED"},
            HTTP_X_CALLBACK_SECRET="supersecret",
        )

        self.assertEqual(response.status_code, 200)
        payment_request.refresh_from_db()
        self.assertEqual(payment_request.status, MobilePaymentRequest.SUCCESSFUL)
        self.assertEqual(payment_request.created_payment, payment)
        self.assertEqual(Payment.objects.filter(reference="mtn-ref-004").count(), 1)
        self.assertTrue(
            PaymentGatewayEvent.objects.filter(
                provider_reference="mtn-ref-004",
                error_message="Payment request already completed.",
                processed=True,
            ).exists()
        )

    @override_settings(
        AIRTEL_MONEY_CALLBACK_SECRET="supersecret",
        FEE_REMINDER_HANDLER="apps.tenant.finance.sms_defaults.log_fee_reminder_to_logger",
    )
    def test_payment_callback_accepts_shared_secret_header(self):
        payment_request = MobilePaymentRequest.objects.create(
            invoice=self.invoice,
            amount=Decimal("25000"),
            phone_number="0752123456",
            network=Payment.AIRTEL_MONEY,
            provider_reference="airtel-ref-001",
            status=MobilePaymentRequest.PROCESSING,
        )

        response = self.client.post(
            reverse("finance_airtel_collection_update"),
            data={"reference": "airtel-ref-001", "status": "SUCCESSFUL"},
            HTTP_X_CALLBACK_SECRET="supersecret",
        )

        self.assertEqual(response.status_code, 200)
        payment_request.refresh_from_db()
        self.assertEqual(payment_request.status, MobilePaymentRequest.SUCCESSFUL)
        self.assertEqual(PaymentGatewayEvent.objects.filter(processed=True).count(), 1)
        self.assertEqual(Payment.objects.filter(reference="airtel-ref-001").count(), 1)


class FinanceAdminCampusScopeTests(TestCase):
    def setUp(self):
        org = get_or_create_organization()
        self.campus = Campus.objects.filter(organization=org).first()
        self.other_campus = Campus.objects.create(
            organization=org,
            name="Other Finance Campus",
            is_active=True,
        )
        self.student = StudentProfile.objects.create(
            first_name="Visible",
            last_name="Finance",
            student_id="FIN-VISIBLE",
            campus=self.campus,
        )
        self.hidden_student = StudentProfile.objects.create(
            first_name="Hidden",
            last_name="Finance",
            student_id="FIN-HIDDEN",
            campus=self.other_campus,
        )
        self.invoice = Invoice.objects.create(student=self.student, reference="INV-VISIBLE")
        self.hidden_invoice = Invoice.objects.create(student=self.hidden_student, reference="INV-HIDDEN")
        self.payment = Payment.objects.create(invoice=self.invoice, amount=Decimal("1000"))
        self.hidden_payment = Payment.objects.create(invoice=self.hidden_invoice, amount=Decimal("2000"))

        campus_role, _ = Role.objects.get_or_create(code=Role.CAMPUS_ADMIN, defaults={"name": "Campus Admin"})
        self.user = User.objects.create_user(username="finance_campus_admin", password="test-pass-123")
        self.user.roles.add(campus_role)
        UserRole.objects.create(user=self.user, role=campus_role, campus=self.campus)

    def test_campus_admin_invoice_list_and_export_ignore_other_campus_filter(self):
        self.client.login(username="finance_campus_admin", password="test-pass-123")

        list_response = self.client.get(reverse("admin_invoices_list"), {"campus": self.other_campus.pk})
        export_response = self.client.get(reverse("admin_invoices_export_csv"), {"campus": self.other_campus.pk})

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "INV-VISIBLE")
        self.assertNotContains(list_response, "INV-HIDDEN")
        self.assertContains(export_response, "INV-VISIBLE")
        self.assertNotContains(export_response, "INV-HIDDEN")

    def test_campus_admin_cannot_access_other_campus_invoice_or_payment_views(self):
        self.client.login(username="finance_campus_admin", password="test-pass-123")

        urls = [
            reverse("admin_invoices_detail", kwargs={"pk": self.hidden_invoice.pk}),
            reverse("admin_invoices_edit", kwargs={"pk": self.hidden_invoice.pk}),
            reverse("admin_invoices_print", kwargs={"pk": self.hidden_invoice.pk}),
            reverse("admin_invoices_clone", kwargs={"pk": self.hidden_invoice.pk}),
            reverse("admin_invoices_carry_forward", kwargs={"pk": self.hidden_invoice.pk}),
            reverse("admin_payment_receipt_pdf", kwargs={"pk": self.hidden_payment.pk}),
            reverse("admin_payments_detail", kwargs={"pk": self.hidden_payment.pk}),
        ]

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_campus_admin_cannot_mutate_other_campus_invoice(self):
        self.client.login(username="finance_campus_admin", password="test-pass-123")

        detail_response = self.client.post(
            reverse("admin_invoices_detail", kwargs={"pk": self.hidden_invoice.pk}),
            {"action": "add_payment", "amount": "100", "method": Payment.CASH},
        )
        line_remove_response = self.client.post(
            reverse("admin_invoices_line_remove", kwargs={"pk": self.hidden_invoice.pk, "line_id": 999999}),
        )
        payment_remove_response = self.client.post(
            reverse("admin_invoices_payment_remove", kwargs={"pk": self.hidden_invoice.pk, "payment_id": self.hidden_payment.pk}),
        )

        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(line_remove_response.status_code, 404)
        self.assertEqual(payment_remove_response.status_code, 404)
        self.assertEqual(self.hidden_invoice.payments.count(), 1)

    def test_campus_admin_cannot_create_invoice_for_other_campus_student(self):
        self.client.login(username="finance_campus_admin", password="test-pass-123")

        response = self.client.post(
            reverse("admin_invoices_create"),
            {
                "student": self.hidden_student.pk,
                "reference": "INV-FORGED",
                "opening_balance": "0",
                "status": Invoice.ACTIVE,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Invoice.objects.filter(reference="INV-FORGED").exists())

    def test_campus_admin_finance_dashboard_is_scoped(self):
        OutboundMessageLog.objects.create(
            message_type=OutboundMessageLog.FEE_REMINDER,
            invoice=self.invoice,
            phone_raw="0772000001",
            status=OutboundMessageLog.FAILED,
            message="visible failure",
        )
        OutboundMessageLog.objects.create(
            message_type=OutboundMessageLog.FEE_REMINDER,
            invoice=self.hidden_invoice,
            phone_raw="0772000002",
            status=OutboundMessageLog.FAILED,
            message="hidden failure",
        )

        self.client.login(username="finance_campus_admin", password="test-pass-123")
        response = self.client.get(reverse("admin_finance_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "INV-VISIBLE")
        self.assertContains(response, "1 active")
        self.assertNotContains(response, "INV-HIDDEN")
        self.assertNotContains(response, "Finance Hidden")

    def test_campus_admin_communication_operations_logs_and_retry_are_scoped(self):
        visible_log = OutboundMessageLog.objects.create(
            message_type=OutboundMessageLog.FEE_REMINDER,
            invoice=self.invoice,
            phone_raw="0772000001",
            status=OutboundMessageLog.FAILED,
            message="visible retry",
        )
        hidden_log = OutboundMessageLog.objects.create(
            message_type=OutboundMessageLog.FEE_REMINDER,
            invoice=self.hidden_invoice,
            phone_raw="0772000002",
            status=OutboundMessageLog.FAILED,
            message="hidden retry",
        )

        self.client.login(username="finance_campus_admin", password="test-pass-123")
        get_response = self.client.get(reverse("admin_finance_communication_operations"))
        post_response = self.client.post(
            reverse("admin_finance_communication_operations"),
            {
                "action": "retry_failed_messages",
                "message_type": OutboundMessageLog.FEE_REMINDER,
                "limit": "20",
                "dry_run": "1",
            },
        )

        self.assertEqual(get_response.status_code, 200)
        self.assertContains(get_response, "0772000001")
        self.assertNotContains(get_response, "0772000002")
        self.assertEqual(post_response.status_code, 302)
        self.assertTrue(
            OutboundMessageLog.objects.filter(
                provider_response__retry_of_log_id=visible_log.pk,
                status=OutboundMessageLog.DRY_RUN,
            ).exists()
        )
        self.assertFalse(
            OutboundMessageLog.objects.filter(
                provider_response__retry_of_log_id=hidden_log.pk,
                status=OutboundMessageLog.DRY_RUN,
            ).exists()
        )
