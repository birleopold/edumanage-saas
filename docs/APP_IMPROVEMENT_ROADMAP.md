# EduManage Improvement Roadmap

This roadmap turns the July 2026 audit into implementation tracks. It favors proof over claims: each item should land with tests, deployment checks, or an operator-facing verification step.

## Current Baseline

- Django system check passes.
- Full local test suite passes with 217 tests.
- Route verification reports 620 URL names, 442 templates, 1,346 template URL references, and 0 broken template references.
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

Status: complete.

Acceptance checks:

- [x] Payment callbacks verify provider signatures or secrets before processing.
- [x] Callback processing is idempotent and replay-safe.
- [x] Webhook retry workers have bounded retries, audit logs, and failure dashboards.
- [x] External API keys have rotation, scope enforcement, and last-used tracking.
- [x] Messaging providers have dry-run, test-send, readiness, and failure-review flows.

## Phase 4: Operational Readiness

Status: complete.

Acceptance checks:

- [x] Production deploy checklist is run before each release.
- [x] Nightly PostgreSQL backup and quarterly restore drill are documented.
- [x] `/health/` and public status routes are monitored externally.
- [x] Error tracking captures stack traces outside the user UI.
- [x] Slow request and slow query thresholds are logged.
- [x] Runbook includes incident response, rollback, backup restore, provider outage, and tenant suspension procedures.

Progress:

- [x] `ObservabilityMiddleware` logs unhandled request exceptions with stack traces and request context through `edumanage.observability`.
- [x] Slow request and high query count warnings are controlled by `SLOW_REQUEST_THRESHOLD_MS` and `SLOW_QUERY_COUNT_THRESHOLD`.
- [x] `check_operational_readiness --strict` verifies observability middleware, logger configuration and performance thresholds.
- [x] `docs/ops/RUNBOOK.md` includes incident response, rollback, backup restore, provider outage and tenant suspension procedures.

## Phase 5: Product Workflow Quality

Status: complete.

Acceptance checks:

- School-owner onboarding can create a tenant, configure branding, add campuses, invite users, and verify first login without developer help.
- Teacher daily workflow covers timetable, attendance, coursework, grading, incidents, and announcements from mobile.
- Parent daily workflow covers fees, attendance, report cards, announcements, documents, and communication preferences from mobile.
- Admin workflow provides fast search, bulk actions, exports, audit trails, and dashboard drill-downs.
- [x] Offline/PWA flows are tested for attendance and high-frequency mobile use.

Progress:

- [x] Platform Create School Wizard records tenant-created audit evidence with owner username, login URL, setup guide URL, campus, academic period, feature flag and schema-context metadata.
- [x] Platform tenant detail now shows a school-owner handoff panel with tenant, domain, DNS, SSL, subscription and first-login readiness checks.
- [x] Regression tests cover the full five-step school creation wizard and the owner handoff pack shown on tenant detail.
- [x] Teacher dashboard shows a data-backed daily workflow across timetable, attendance, coursework, grading, incidents and announcements.
- [x] Parent dashboard shows a data-backed family workflow across fees, attendance, report cards, announcements, documents and communication preferences.
- [x] Admin dashboard shows a workflow rail for fast search, bulk actions, exports, audit trails, recovery evidence and dashboard drill-downs.
- [x] Offline attendance tests cover replay-safe JSON sync, idempotent updates, roll-call wiring, take-attendance wiring, PWA install metadata and service-worker caching for teacher attendance routes.

## Phase 6: Dependency Lifecycle

Status: complete.

Acceptance checks:

- [x] Upgrade path from Django 4.2 to a supported LTS line is tested on a branch.
- [x] Dependencies are reviewed monthly for security and support status.
- [x] Release notes are checked before major framework upgrades.
- [x] CI pins supported Python and Node versions.

Progress:

- [x] Django is pinned to `5.2.16` LTS and `django-tenants` is pinned to `3.10.2`, replacing the unsupported Django 4.2 stack.
- [x] `check_dependency_lifecycle --strict` verifies Django LTS, django-tenants compatibility, Python/Node runtime pins, CI wiring and monthly review documentation.
- [x] CI runs the dependency lifecycle gate before Django checks and tests.
- [x] `docs/ops/DEPENDENCY_LIFECYCLE.md` records monthly review cadence, release-note review expectations and the 4.2-to-5.2 compatibility finding.

## Working Rule

Do not call the app production-ready because a feature exists. Call it production-ready only when the feature has permission tests, unhappy-path behavior, deployment checks, and an operator recovery path.
