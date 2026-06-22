# Exam Review Console

This feature adds a dedicated admin review area for online exam monitoring and follow-up.

## Routes

- `/admin/exams/review/`
- `/admin/exams/review/export/`
- `/admin/exams/review/attempts/<id>/`
- `/admin/exams/review/events/<id>/`
- `/admin/exams/review/events/<id>/resolve/`

## Dashboard filters

The dashboard supports filtering by:

- exam,
- paper,
- student name or student ID,
- event type,
- IP address,
- minimum warning count.

## Attempt review

The attempt review page shows:

- exam paper,
- student,
- attempt status,
- start and submit IP addresses,
- browser focus warning count,
- lock timestamp,
- lock reason,
- event timeline,
- submitted responses and marks.

## Event review

The event page shows:

- event type,
- student and paper,
- timestamp,
- IP address,
- user agent,
- metadata,
- review status and notes.

Review status is stored in the existing event metadata JSON, so no database schema change is required.

## Export

The CSV export produces a follow-up file with:

- attempt ID,
- exam,
- paper,
- student,
- status,
- timestamps,
- IP addresses,
- warning count,
- lock reason,
- event count.

## Suggested verification

Run Django checks and smoke-test:

- opening the review dashboard,
- applying each filter,
- opening an attempt timeline,
- opening an event detail,
- saving a review status and note,
- exporting CSV for filtered records.
