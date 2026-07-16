# EduManage Improvement Roadmap

This roadmap turns the July 2026 audit into implementation tracks. It favors proof over claims: each item should land with tests, deployment checks, or an operator-facing verification step.

## Current Baseline

- Django system check passes.
- Full local test suite passes with 196 tests.
- Route verification reports 620 URL names, 442 templates, 1,331 template URL references, and 0 broken template references.
- Node production dependency audit reports 0 vulnerabilities.
- Main risks are production hardening, dependency lifecycle, campus/tenant access-control proof, and day-two operations.

## Phase 1: Release Gates and Production Hardening

Status: in progress.

Acceptance checks:

- CI runs `python manage.py check`.
- CI runs `python manage.py check --deploy` with `config.settings.prod`.
- CI runs `python verify_routes.py`.
- CI runs the Django test suite.
- CI runs `npm audit --omit=dev`.
- Production settings enforce secure cookies, SSL redirect, HSTS, content sniffing protection, referrer policy, and frame protection.
- `.env.production.example` points at `config.settings.prod`, not tenant settings directly.

## Phase 2: Access Control and Campus/Tenant Isolation

Status: in progress.

Acceptance checks:

- Every admin, teacher, student, and parent view has an explicit role gate.
- Every object detail/edit/export endpoint filters by server-side ownership or campus scope before fetching by primary key.
- Campus-admin tests cover list, detail, create, update, export, dashboard, and retry workflows for every sensitive module.
- Parent/student/teacher self-service tests prove users cannot access another user's records by changing URL IDs.
- Tenant isolation is tested under PostgreSQL schemas before production onboarding.

High-priority modules:

- Finance, assessments/results, attendance, sickbay, documents, students, parents, HR/payroll, analytics, reports, library, hostels, transport.

## Phase 3: Provider and Webhook Trust

Status: in progress.

Acceptance checks:

- [x] Payment callbacks verify provider signatures or secrets before processing.
- [x] Callback processing is idempotent and replay-safe.
- Webhook retry workers have bounded retries, audit logs, and failure dashboards.
- [x] External API keys have rotation, scope enforcement, and last-used tracking.
- Messaging providers have dry-run, test-send, readiness, and failure-review flows.

## Phase 4: Operational Readiness

Status: next.

Acceptance checks:

- Production deploy checklist is run before each release.
- Nightly PostgreSQL backup and quarterly restore drill are documented.
- `/health/` and public status routes are monitored externally.
- Error tracking captures stack traces outside the user UI.
- Slow request and slow query thresholds are logged.
- Runbook includes incident response, rollback, backup restore, provider outage, and tenant suspension procedures.

## Phase 5: Product Workflow Quality

Status: planned.

Acceptance checks:

- School-owner onboarding can create a tenant, configure branding, add campuses, invite users, and verify first login without developer help.
- Teacher daily workflow covers timetable, attendance, coursework, grading, incidents, and announcements from mobile.
- Parent daily workflow covers fees, attendance, report cards, announcements, documents, and communication preferences from mobile.
- Admin workflow provides fast search, bulk actions, exports, audit trails, and dashboard drill-downs.
- Offline/PWA flows are tested for attendance and high-frequency mobile use.

## Phase 6: Dependency Lifecycle

Status: planned.

Acceptance checks:

- Upgrade path from Django 4.2 to a supported LTS line is tested on a branch.
- Dependencies are reviewed monthly for security and support status.
- Release notes are checked before major framework upgrades.
- CI pins supported Python and Node versions.

## Working Rule

Do not call the app production-ready because a feature exists. Call it production-ready only when the feature has permission tests, unhappy-path behavior, deployment checks, and an operator recovery path.
