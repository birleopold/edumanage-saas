# Operations runbook (EduManage SaaS)

Plain-language checks and commands for day-two operations. Paths are from the repo root `edumanage_saas/` unless noted.

## Health and status

- **Staff-facing checks** (authenticated admin): open **System status** in the admin portal (`admin_system_status`). Uses the same readiness logic as automation.
- **Public status** (no login): `GET /status/` returns HTML; append `?format=json` or send `Accept: application/json` for machine-readable output. Safe for uptime monitors—no secrets in the payload.
- **External monitoring plan**: configure probes and infrastructure alerts from `docs/ops/MONITORING.md`.
- **Disable public status** (e.g. private deployment): set `PUBLIC_STATUS_PAGE_ENABLED=false` in environment (see `config/settings/base.py`).

- **Accessibility (roadmap scope):** hot-path WCAG 2.1 AA-oriented implementation and checklist — `docs/accessibility/WCAG_HOT_PATH_SIGNOFF.md`.

## Messaging and webhooks

- **Webhook retry queue**: scheduled job should run `python manage.py process_webhook_retry_queue` (interval depends on volume; many teams use every 1–5 minutes).
- **Communication templates**: fee reminders, payment receipts, absence alerts, and urgent broadcasts use **active** `CommunicationTemplate` rows when present. Staff edit copy in Django admin; placeholders are documented in the **Communication Hub** UI (`communication_center.html`).
- **Integration probe** (if exposed): `GET /api/v1/integrations/health/` (see project API docs).

## Bulk student import

- CSV flow is **preview then confirm**: upload runs validation and shows rows; **Confirm import** applies rows from server-side cache (short TTL). If confirm fails with an expired token, re-run preview.
- **Cache**: `CACHES` defaults to in-memory per process; for multi-worker production, switch to Redis or another shared cache so preview tokens are visible to all workers.
- **Automated tests (Django 5+)**: for `multipart/form-data` views, put the uploaded file on the same `data` dict as other fields (for example `post(url, {"action": "preview", "import_file": uploaded})`). A separate `files=` keyword alone may not populate `request.FILES` in the test client.

## Tenant database and migrations

- Run migrations per tenant/environment policy (often `python manage.py migrate_schemas` or `migrate` on the correct schema—follow your deployment doc).
- After pulling code, apply new migrations before relying on template or bulk-import behavior.

## Backups and recovery (baseline)

- **Database**: follow your host’s automated backup schedule; test a restore quarterly.
- **Nightly evidence**: after an automated backup completes, record it in the app audit trail with `python manage.py record_backup --status SUCCESS --file-path <backup-uri> --checksum <sha256>`.
- **Quarterly restore drill evidence**: after restoring into staging and smoke-testing login, tenant access, finance reports, and document/media access, record `python manage.py record_backup --status RESTORE_TESTED --notes "Restored <date> backup into staging and verified smoke tests"`.
- **Secrets**: WhatsApp/SMS provider keys and Django `SECRET_KEY` must be restored from a secure vault, not from application DB backups alone.
- **Incident communication**: use the public status page or external status vendor if the app is unreachable; update `PUBLIC_STATUS_PAGE_ENABLED` only if the route must be hidden during an investigation.

## Quick reference — environment

| Variable (examples) | Purpose |
|---------------------|---------|
| `PUBLIC_STATUS_PAGE_ENABLED` | `true`/`false` — toggles `/status/`. |
| `SUPPORT_CONTACT_EMAIL` | Shown in footers for support tickets. |
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
