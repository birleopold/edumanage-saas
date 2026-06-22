# Polls Portal

This feature exposes the existing polls app in tenant portals.

## Routes

Management:

- `/admin/polls/`
- `/admin/polls/create/`
- `/admin/polls/<id>/`
- `/admin/polls/<id>/edit/`
- `/admin/polls/<id>/toggle/`
- `/admin/polls/<id>/options/add/`

Participation:

- `/polls/`
- `/polls/<id>/`
- `/polls/<id>/vote/`
- `/polls/<id>/results/`

Role aliases:

- `/teacher/polls/`
- `/student/polls/`
- `/parent/polls/`

## Included capabilities

- Admin poll creation and editing.
- Audience and campus targeting.
- Specific student and teacher targeting.
- Publish and unpublish flow.
- Option management.
- Portal response cards for eligible users.
- Result summaries.
- Availability-window checks.
- Dashboard card component prepared at `templates/components/portal_poll_cards.html`.

## Suggested verification

Run Django checks and smoke-test management, response, result visibility and expiry flows in a tenant environment.
