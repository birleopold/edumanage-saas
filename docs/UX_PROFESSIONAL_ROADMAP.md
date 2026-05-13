# Professional UX & operations roadmap (EduManage SaaS)

This roadmap translates research-backed product UX (role clarity, onboarding, plain-language errors, trust, and operations) into concrete work. Status below reflects implementation in the codebase.

## Phase A — Orientation & trust (foundation)

| Item | Status | Notes |
|------|--------|--------|
| “Where am I?” school + campus context in admin header | Done | `portals/admin/base.html` |
| Support reference (tenant schema) for help tickets | Done | `orgsettings.context_processors` + footers |
| Optional `SUPPORT_CONTACT_EMAIL` in env | Done | `config/settings/base.py` |
| Communication Hub (single entry: reports, templates, links) | Done | `admin_communication_center` |
| School setup checklist (guided links, not duplicate forms) | Done | `admin_school_setup_guide` |
| Staff-facing system status (plain language) | Done | `admin_system_status` |
| Default message templates (editable library) | Done | `CommunicationTemplate` model + admin |

## Phase B — Role dashboards & non-tech language

| Item | Status | Notes |
|------|--------|--------|
| Admin dashboard: setup progress + Communication Hub link | Done | `admin/home.html` |
| Teacher dashboard: academic context + class count | Done | `teacher_home` |
| Parent dashboard: message preferences summary + link | Done | `parent/home.html` + preferences page |
| Parent self-service: SMS / WhatsApp alert toggles | Done | `parent_communication_preferences` |

## Phase C — Branding & accessibility baseline

| Item | Status | Notes |
|------|--------|--------|
| Org colors on teacher / parent / student portals | Done | `:root` vars + sidebar header |
| School name in non-admin sidebars | Done | Uses `org_profile.name` |
| Skip link + focus states (existing) | Kept | Already in base templates |

## Phase D — Deeper UX (next iterations)

| Item | Status | Notes |
|------|--------|--------|
| Wire `CommunicationTemplate` bodies into send flows | Done | `finance/outbound_copy.py` + `finance/services.py` `build_*` |
| Guided product tour (optional, skippable) | Done | `components/admin_product_tour.html` + `portals/admin/base.html` |
| Import wizard with row-level preview | Done | `students/bulk_views.py` preview/confirm + `bulk_import_preview.html` |
| Public or separately hosted status page | Done | `portals/public_views.py` `public_status`, `/status/` |
| WCAG audit (contrast, forms, ARIA) | Done | Hot-path WCAG 2.1 AA-oriented pass documented in `docs/accessibility/WCAG_HOT_PATH_SIGNOFF.md` (all portals, auth, public status, toasts, tour, bulk import). Full product sweep = extend same checklist to remaining screens. |

## Phase E — Professional operations

| Item | Status | Notes |
|------|--------|--------|
| Runbooks / backup drills | Done | See `docs/ops/RUNBOOK.md` |
| Integration health (API) | Exists | `/api/v1/integrations/health/` |
| Webhook retry processing | Exists | `process_webhook_retry_queue` command |

---

## How to use this roadmap

1. **New school**: send admins to **Getting started checklist** (`/admin/school-setup/`).
2. **Messaging**: use **Communication Hub** (`/admin/communication/`) then Messaging Report and templates.
3. **Support**: ask staff to quote **School reference** from the portal footer when contacting support.
