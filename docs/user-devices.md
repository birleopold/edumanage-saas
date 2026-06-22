# User Devices

This feature exposes the existing `MobileDevice` model outside Django admin.

## User pages

- `/profile/devices/` lists a signed-in user's mobile and PWA devices.
- `/profile/devices/<id>/disable/` lets the user turn off an old device.

The profile page now links to My Devices from the Security section.

## Admin monitoring

- `/admin/users/devices/` lets administrators review registered devices.

Admin filters include user search, platform, active status, and alert readiness. Sensitive device credentials are not shown in the admin UI.

## API endpoints

- `GET /api/v1/mobile/devices/`
- `POST /api/v1/mobile/devices/register/`
- `POST /api/v1/mobile/devices/token/`
- `POST /api/v1/mobile/devices/<id>/disable/`

API responses show whether a device is ready for mobile alerts without returning raw credentials.

## Notification connection

The notification center can use this device list later when sending mobile or PWA alerts. This PR keeps active devices, app versions, platform values, last-seen time, and alert readiness current.

## Suggested verification

Run Django checks and smoke-test profile devices, admin device monitor, registration, token refresh, and disable flows in a tenant environment.
