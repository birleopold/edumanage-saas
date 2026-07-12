# PWA Devices

This feature exposes browser push subscriptions outside Django admin so users
and administrators can manage PWA alert access from the normal portal.

## User Pages

- `/profile/devices/` lists a signed-in user's PWA browser subscriptions.
- `/profile/devices/<id>/disable/` lets the user turn off alerts for an old browser.

The profile page links to My Devices from the Security section.

## Admin Monitoring

- `/admin/users/devices/` lets administrators review PWA alert registrations.
- `/admin/users/devices/test-push/` sends a test alert to the signed-in admin's
  active browser subscriptions.

Admin filters include user search, active status, alert readiness, and delivery
errors. Raw browser push credentials are not shown in the admin UI.

## API Endpoints

The legacy `/api/v1/mobile/devices/` endpoints may remain for integrations, but
the first-class portal experience is the Django PWA browser flow:

- `/pwa/push-readiness/`
- `/pwa/push-subscribe/`
- `/pwa/push-unsubscribe/`

## Notification Connection

Portal alerts use `WebPushSubscription` records and the Python web-push helper.
No separate mobile Node project is required.

Generate VAPID keys with:

```bash
python manage.py generate_vapid_keys --subject mailto:admin@example.com
```

Add the printed `WEB_PUSH_PUBLIC_KEY`, `WEB_PUSH_PRIVATE_KEY`, and
`WEB_PUSH_SUBJECT` values to the deployment environment.

## Suggested Verification

Run Django checks and smoke-test profile devices, admin alert monitor, PWA
subscription, unsubscribe, and the admin Send test alert action in a tenant
environment.
