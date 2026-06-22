# Transport Schedules and Notifications

This rollout strengthens the transport module beyond the existing route, vehicle, stop, and assignment screens.

## Admin routes

- `/admin/transport/schedules/`
- `/admin/transport/schedules/create/`
- `/admin/transport/schedules/<id>/edit/`
- `/admin/transport/notices/`
- `/admin/transport/notices/create/`

## Parent routes

- `/parent/transport/`
- `/parent/transport/assignments/<id>/`

## Student routes

- `/student/transport/`
- `/student/transport/assignments/<id>/`

## Included capabilities

- Admin route schedule list, create, and edit.
- Admin transport notice list and composer.
- Notice presets for departed, arrived, delay, and route change messages.
- Parent overview with linked child transport records.
- Parent detail page showing route, stop, assigned vehicle, driver, schedule, latest tracking, and notice history.
- Student overview and detail page showing route, stop, assigned vehicle, driver, schedule, and latest tracking.

## Existing model reuse

The implementation uses the existing models:

- `RouteSchedule`
- `VehicleTracking`
- `ParentNotification`
- `StudentTransportAssignment`
- `TransportRoute`
- `RouteStop`
- `Vehicle`
- `Driver`

No database schema changes are required.

## Suggested verification

Run Django checks and smoke-test:

- create and edit route schedules,
- create notices using the presets,
- verify parents see only linked children,
- verify students see only their own transport assignment,
- confirm latest vehicle tracking appears when tracking logs exist,
- confirm schedule and notice history render on detail pages.
