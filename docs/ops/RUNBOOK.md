# Operations runbook (EduManage SaaS)

Plain-language checks and commands for day-two operations. Paths are from the repo root `edumanage_saas/` unless noted.

## Health and status

- **Staff-facing checks**: open **System status** in the admin portal (`admin_system_status`). Uses the same readiness logic as automation.
- **Public status**: `GET /status/` returns HTML; append `?format=json` or send `Accept: application/json` for machine-readable output. Safe for uptime monitors because no secrets are included.
- **External monitoring plan**: configure probes and infrastructure alerts from `docs/ops/MONITORING.md`.
- **Disable public status**: set `PUBLIC_STATUS_PAGE_ENABLED=false` in environment.
- **Error tracking**: unhandled request exceptions are logged by `apps.tenant.audit.observability.ObservabilityMiddleware` through the `edumanage.observability` logger with stack traces and request context. Ship this logger to the host log drain or error tracker.
- **Performance thresholds**: set `SLOW_REQUEST_THRESHOLD_MS` and `SLOW_QUERY_COUNT_THRESHOLD` in production. Defaults are `1500` ms and `75` queries.
- **Accessibility**: hot-path WCAG 2.1 AA-oriented implementation and checklist lives at `docs/accessibility/WCAG_HOT_PATH_SIGNOFF.md`.

## Messaging and webhooks

- **Webhook retry queue**: scheduled job should run `python manage.py process_webhook_retry_queue` every 1-5 minutes depending on volume.
- **Communication templates**: fee reminders, payment receipts, absence alerts, and urgent broadcasts use active `CommunicationTemplate` rows when present. Staff edit copy in Django admin; placeholders are documented in the Communication Hub UI (`communication_center.html`).
- **Integration probe**: if exposed, check `GET /api/v1/integrations/health/`.

## Bulk student import

- CSV flow is **preview then confirm**: upload runs validation and shows rows; **Confirm import** applies rows from server-side cache. If confirm fails with an expired token, re-run preview.
- **Cache**: `CACHES` defaults to in-memory per process. For multi-worker production, switch to Redis or another shared cache so preview tokens are visible to all workers.
- **Automated tests (Django 5+)**: for `multipart/form-data` views, put the uploaded file on the same `data` dict as other fields, for example `post(url, {"action": "preview", "import_file": uploaded})`.

## Tenant database and migrations

- Run migrations per tenant/environment policy, often `python manage.py migrate_schemas` or `migrate` on the correct schema.
- After pulling code, apply new migrations before relying on template or bulk-import behavior.

## Incident response

1. Confirm impact from `/health/`, `/status/?format=json`, host metrics, and recent `edumanage.observability` errors.
2. Assign an incident owner, note start time, affected tenants, affected modules, and customer-visible symptoms.
3. Freeze unrelated deploys and risky admin changes until the incident owner clears them.
4. Mitigate first: disable optional providers, pause retry workers, roll back the release, or suspend a tenant if that contains impact.
5. Communicate status from the public status page or external status vendor. Avoid exposing tenant data, secrets, stack traces, or provider credentials.
6. After recovery, record timeline, root cause, customer impact, rollback/restore evidence, and follow-up tasks.

## Rollback

1. Identify the last known good commit, image, or release artifact.
2. Stop background workers that could process incompatible jobs while the app is rolling back.
3. Restore the previous artifact and environment variables. Do not roll back database migrations unless a tested reverse migration or restore plan exists.
4. Run smoke checks: login, tenant routing, invoice list/export, attendance save, messaging readiness, `/health/`, and `/status/?format=json`.
5. Restart workers and watch `edumanage.observability` plus provider retry dashboards for at least one retry interval.

## Backups and recovery

- **Database**: follow your host automated backup schedule; test a restore quarterly.
- **Nightly evidence**: after an automated backup completes, record it in the app audit trail with `python manage.py record_backup --status SUCCESS --file-path <backup-uri> --checksum <sha256>`.
- **Quarterly restore drill evidence**: after restoring into staging and smoke-testing login, tenant access, finance reports, and document/media access, record `python manage.py record_backup --status RESTORE_TESTED --notes "Restored <date> backup into staging and verified smoke tests"`.
- **Secrets**: WhatsApp/SMS provider keys and Django `SECRET_KEY` must be restored from a secure vault, not from application DB backups alone.
- **Restore order**: restore database, restore media/documents, restore secrets from vault, run migrations only if required by the target release, then smoke-test tenant login, finance reports, attendance, documents and provider readiness.
- **Incident communication**: use the public status page or external status vendor if the app is unreachable; update `PUBLIC_STATUS_PAGE_ENABLED` only if the route must be hidden during an investigation.

## Provider outage

- **Payments**: keep callback signature checks enabled. Mark the provider degraded in status communication, pause manual retries if callbacks are failing globally, and reconcile pending payments once callbacks resume.
- **SMS/WhatsApp**: switch fee reminders to dry-run or a backup channel when possible. Keep retry workers bounded and review failed message logs before replaying.
- **Email**: pause non-critical bulk sends, keep password-reset/support paths prioritized, and document any queued messages that need replay.
- **Push/PWA**: failed push delivery should not block core portal workflows. Use in-app notifications or SMS for urgent messages while push is degraded.

## Tenant suspension

1. Confirm authority to suspend: billing, legal, security abuse, or owner request.
2. Capture tenant identifier, domain, requester, reason, and expected review date in the audit trail or incident notes.
3. Disable or redirect tenant access using the platform tenant controls for that deployment. Keep public platform health routes available.
4. Pause tenant-specific background jobs, outbound messaging, imports, and payment collection if required by the suspension reason.
5. Preserve tenant data and backups. Do not delete schemas or media as part of suspension.
6. To reinstate, verify authorization, re-enable tenant/domain access, run login and billing smoke checks, then restart tenant-specific jobs.

## Quick reference - environment

| Variable | Purpose |
|----------|---------|
| `PUBLIC_STATUS_PAGE_ENABLED` | `true`/`false`; toggles `/status/`. |
| `SUPPORT_CONTACT_EMAIL` | Shown in footers for support tickets. |
| `OBSERVABILITY_LOG_LEVEL` | Logger level for request exception and performance telemetry. |
| `SLOW_REQUEST_THRESHOLD_MS` | Request duration warning threshold in milliseconds. |
| `SLOW_QUERY_COUNT_THRESHOLD` | Per-request query count warning threshold. |
| Messaging provider vars | As documented in `docs/WHATSAPP_PHASE1_SETUP.md` or your integrator setup. |

For detailed product UX status, see `docs/UX_PROFESSIONAL_ROADMAP.md`.

## Release gates

Run these before merging or deploying:

```bash
python manage.py check_operational_readiness --strict
python manage.py check_dependency_lifecycle --strict
python manage.py check
DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py check --deploy
python verify_routes.py
python manage.py test
npm audit --omit=dev
```

Production must use `config.settings.prod`. It enables HTTPS-oriented settings such as secure cookies, SSL redirect, HSTS, frame protection, content-type sniffing protection, and a same-origin referrer policy. If SSL redirect or HSTS is terminated outside Django, keep the proxy configuration documented with the release notes.

Dependency support windows are release gates too. See `docs/ops/DEPENDENCY_LIFECYCLE.md` for the monthly dependency review, Django LTS policy, and release-note review procedure.

For the implementation roadmap and acceptance checks, see `docs/APP_IMPROVEMENT_ROADMAP.md`.
