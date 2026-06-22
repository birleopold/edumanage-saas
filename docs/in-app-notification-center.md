# In-app Notification Center

This feature exposes the existing tenant `Notification` model to portal users.

## User routes

- `/notifications/` - notification inbox for admins, teachers, students and parents.
- `/notifications/<id>/read/` - marks a notification as read and redirects to its linked portal page when available.
- `/notifications/mark-all-read/` - marks all visible notifications as read for the logged-in user.

## Admin route

- `/notifications/compose/` - admin/campus-admin composer for urgent alerts, fee reminders, exam alerts, transport alerts and system notices.

## Bell dropdown

The admin, teacher, student and parent base templates already include a bell dropdown. The orgsettings context processor now sends the bell recent notification items through the read route so clicking a bell item can update read status.

## Targeting

The composer supports:

- one direct recipient,
- audience targeting,
- campus targeting,
- priority levels,
- optional portal links,
- expiry dates,
- creator tracking.

The composer expands audience/campus targets into user-specific notification rows. This keeps read status personal for users instead of relying on one broadcast row for everyone.

## Suggested verification

Run Django checks and smoke-test these flows in a tenant environment:

- admin composes a system notice for all users,
- teacher sees bell badge and inbox item,
- student marks one item as read,
- parent uses mark all read,
- expired notification disappears from the inbox,
- campus admin only targets users in their campus scope.
