from decimal import Decimal
import hashlib
import hmac
import json

from django.test import Client
from django.test import TestCase, override_settings

from apps.tenant.announcements.models import Announcement
from apps.tenant.finance.models import (
    CommunicationTemplate,
    IntegrationApiKey,
    Invoice,
    OutboundMessageLog,
    Payment,
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
from apps.tenant.students.models import StudentProfile


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
        response = self.client.get(
            "/api/v1/integrations/message-logs/",
            HTTP_X_API_KEY=raw_key,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("results", payload)

    @override_settings(FEE_REMINDER_CHANNEL="SMS")
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
