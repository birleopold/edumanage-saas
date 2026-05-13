# WhatsApp Phase 1 Setup (Fee Reminders)

This project now supports Phase 1 delivery through WhatsApp for:

- Fee reminders
- Payment receipt messages (with direct receipt link)

Phase 2 additions:
- Attendance absence alerts
- Urgent announcement broadcasts
- Parent communication consent flags (SMS/WhatsApp)
- Messaging report page for campaign/reporting

## What was added

- Channel-aware reminder dispatch (`SMS` or `WHATSAPP`)
- WhatsApp phone normalization (E.164 digits format)
- Optional parent invoice link in reminder text
- WhatsApp Cloud API handler
- Delivery audit trail (`finance.OutboundMessageLog`)
- Backward compatibility with existing `FEE_REMINDER_SMS_HANDLER`

## Environment variables

Add these to your `.env`:

```env
FEE_REMINDER_CHANNEL=WHATSAPP
FEE_REMINDER_HANDLER=apps.tenant.finance.whatsapp_defaults.send_fee_reminder_whatsapp_cloud_api
FEE_REMINDER_DEFAULT_COUNTRY_CODE=256
FEE_REMINDER_PORTAL_BASE_URL=https://your-tenant-domain.example.com

WHATSAPP_CLOUD_ACCESS_TOKEN=your_meta_access_token
WHATSAPP_CLOUD_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_CLOUD_API_VERSION=v20.0
WHATSAPP_CLOUD_TIMEOUT_SECONDS=15
FEE_RECEIPT_AUTO_SEND_ON_PAYMENT=false
```

If you want to test without external API calls:

```env
FEE_REMINDER_CHANNEL=WHATSAPP
FEE_REMINDER_HANDLER=apps.tenant.finance.whatsapp_defaults.log_fee_reminder_whatsapp_to_logger
```

## How to use

- **Admin UI (fee reminder):** open any invoice with outstanding balance and click **Send fee reminder to parents**.
- **Admin UI (payment receipt):** in the invoice payments table, click **Send** in the Message column for a payment row.
- **Command line:**

```bash
python manage.py send_fee_reminders --overdue
python manage.py send_fee_reminders --invoice-id=42
python manage.py send_fee_reminders --overdue --dry-run
python manage.py check_finance_messaging_readiness
python manage.py retry_outbound_messages --dry-run
python manage.py retry_outbound_messages --limit=50 --message-type=FEE_REMINDER
python manage.py send_absence_alerts --date=2026-05-04 --dry-run
python manage.py broadcast_urgent_announcement --announcement-id=12 --dry-run
```

## Notes

- If `FEE_REMINDER_HANDLER` is not set, reminders are logged and marked as dispatched (safe fallback).
- `FEE_REMINDER_SMS_HANDLER` still works for legacy configurations.
- WhatsApp normalization assumes local numbers should be expanded with `FEE_REMINDER_DEFAULT_COUNTRY_CODE`.
- If `FEE_RECEIPT_AUTO_SEND_ON_PAYMENT=true`, payment receipt messages are sent automatically after payment capture.
