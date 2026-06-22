# Integrations Center

This feature expands the custom admin integrations UI beyond provider basics.

## Route

- `/admin/integrations/`
- `/admin/integrations/tabs/<tab>/`

## Tabs

The center includes tabs for:

- Providers
- API Keys
- Scopes
- Webhooks
- Webhook Deliveries
- Retry Queue
- Inbound Events
- SSO Providers
- Biometric Devices
- Biometric Events
- Meeting Links
- Event Logs

## Operations

The first rollout supports:

- masked provider credentials in the center list,
- provider test logging/queueing,
- API key creation,
- API key rotation,
- API key activation/deactivation,
- scope creation,
- webhook endpoint creation,
- generated webhook secrets,
- test webhook queue item creation,
- retry queue item immediate retry scheduling,
- last-used visibility for integration keys,
- event, delivery, inbound, biometric and meeting-link monitoring.

## Security notes

- API key hashes are never displayed.
- Key prefixes are shown only for identification.
- New and rotated keys are shown once through the success message so they can be copied immediately.
- Provider secrets are masked in tables.
- The provider edit form uses password-style inputs for secret fields.

## Suggested verification

Run Django checks and smoke-test:

- opening all tabs,
- creating a key and assigning scopes,
- rotating a key,
- disabling/enabling a key,
- creating a webhook endpoint,
- queueing a webhook test,
- moving a retry item to immediate retry,
- queueing/logging a provider test,
- opening provider edit with secret fields.
