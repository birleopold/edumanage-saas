# Communication Providers

EduManage now routes outbound school communication through real provider handlers.

## SMS gateway settings

Set these in the deployment environment:

```env
SMS_GATEWAY_URL=
SMS_GATEWAY_TOKEN=
SMS_GATEWAY_SENDER_ID=EduManage
SMS_GATEWAY_TIMEOUT_SECONDS=15
```

The generic SMS handler sends JSON with `to`, `message`, and `sender_id`.

## WhatsApp Cloud API settings

Set these in the deployment environment:

```env
WHATSAPP_CLOUD_ACCESS_TOKEN=
WHATSAPP_CLOUD_PHONE_NUMBER_ID=
WHATSAPP_CLOUD_API_VERSION=v20.0
WHATSAPP_CLOUD_TIMEOUT_SECONDS=15
```

## Handler setting

The default handler is:

```env
FEE_REMINDER_HANDLER=apps.tenant.finance.communication_providers.send_fee_message_provider
```

If no real SMS or WhatsApp credentials are configured, provider sending fails instead of returning fake success. Use dry-run options only for tests and demos.
