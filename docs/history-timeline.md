# Reusable History Timeline

This feature exposes generic `StatusHistory` and `ActionLog` records in the custom portal UI.

## Component

The reusable template tag is:

```django
{% load history_tags %}
{% history_timeline object "Timeline title" %}
```

It combines records from:

- `StatusHistory`
- `ActionLog`

for the supplied model instance using Django content types and object IDs.

## Timeline fields

The component shows:

- old status,
- new status,
- actor,
- reason or description,
- timestamp,
- metadata.

## Attached pages

The first rollout adds timelines to:

- applicant/admission detail,
- invoice detail,
- payment/transaction detail,
- discipline incident detail,
- grievance detail,
- transport assignment detail and edit screen.

## Notes

The component is generic, so it can be added to any future detail page by loading `history_tags` and calling `history_timeline` with the page object.

## Suggested verification

Run Django checks and open each attached detail page in a tenant environment. Records with existing `StatusHistory` or `ActionLog` entries should show a populated timeline; records without history should show the empty state.
