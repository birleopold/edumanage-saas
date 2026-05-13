# Phase 3 Integrations (API + Webhooks)

This document summarizes the Phase 3 integration layer implemented for EduManage SaaS.

## What is included

- API-key secured integration endpoints under `/api/v1/integrations/`
- Outbound webhook endpoint subscriptions
- Webhook delivery logging per event
- Automatic webhook event trigger when an `OutboundMessageLog` row is created
- Outbound webhook retry queue with backoff
- Signed inbound WhatsApp delivery-status callback receiver

## Models

Added in `apps.tenant.finance.models`:

- `IntegrationApiKey`
  - Stores hashed API keys (`key_hash`), never plaintext
  - Includes key prefix and `last_used_at`
- `WebhookEndpoint`
  - External callback URL and event subscription
  - Current event: `message_log.created`
- `WebhookDelivery`
  - Delivery audit rows with payload, HTTP status, response/error

## API endpoints

All require `X-API-Key` header.

- `GET /api/v1/integrations/health/`
- `GET /api/v1/integrations/message-logs/?limit=50&status=FAILED&message_type=FEE_REMINDER&channel=WHATSAPP`
- `GET /api/v1/integrations/webhook-deliveries/?limit=50&success=false`
- `POST /api/v1/integrations/callbacks/whatsapp-status/` (HMAC signed)

## Create API key

```bash
python manage.py create_integration_api_key --name "Zapier Connector"
```

Store the output key securely; plaintext is shown once.

## Webhook signature

Outgoing webhook requests include:

- `X-Webhook-Event`
- `X-Webhook-Signature-256`

Signature uses HMAC SHA-256 over raw JSON payload with endpoint secret.

## Settings

```env
WEBHOOK_REQUEST_TIMEOUT_SECONDS=8
WEBHOOK_MAX_RETRY_ATTEMPTS=5
WEBHOOK_RETRY_BASE_SECONDS=30
WHATSAPP_STATUS_WEBHOOK_SECRET=replace_with_shared_secret
```

## Notes

- Webhook delivery is best-effort and non-blocking for core user flow (errors are logged in `WebhookDelivery`).
- Integration endpoints are intentionally read-focused in Phase 3 MVP.
- Process retry queue periodically:
  - `python manage.py process_webhook_retry_queue --limit=200`
