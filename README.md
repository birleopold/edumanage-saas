# EduManage SaaS — School Management System

EduManage SaaS is a Django-based school management platform for administration, academic records, finance, communication, reporting and school operations. It supports PostgreSQL schema-based multi-tenancy through `django-tenants`, while retaining a simple SQLite development mode.

## Main features

### Core modules

- **Multi-tenancy:** PostgreSQL schema isolation through `django-tenants`.
- **User management:** Role-based access for platform staff, school administrators, campus administrators, teachers, students and parents.
- **Academic management:** Academic years, terms, levels, programmes, streams, courses, offerings and enrolment.
- **Student management:** Student profiles, academic records and parent links.
- **Teacher management:** Teacher profiles, course assignments, attendance and grading workflows.
- **Admissions:** Application processing and learner onboarding.
- **Attendance:** Session-based attendance, roll call and privacy-conscious offline drafts.
- **Assessments and examinations:** Assessment capture, grading, exam papers and results.
- **Finance:** Fees, invoices, payments, reminders, receipts and accounting posting.
- **Library:** Book catalogue, inventory and loan management.
- **Timetable:** Period scheduling, rooms and class timetables.
- **Transport:** Route management and learner transport assignments.
- **Hostel:** Accommodation and bed allocation.
- **Discipline:** Incident recording and disciplinary actions.
- **Inventory:** Asset tracking and assignments.
- **Documents:** File sharing with audience targeting.
- **Announcements:** School communication and notices.
- **Reports:** Analytics and exports.

### Branding and customisation

- Organisation-level branding.
- Campus-level logo and branding overrides.
- Custom primary and secondary colours.

## Technology

- **Backend:** Django 5.2 LTS
- **Multi-tenancy:** django-tenants
- **Database:** SQLite for local development; PostgreSQL for SaaS and production
- **API:** Django REST Framework
- **Frontend:** Django templates and committed static CSS/JavaScript
- **Static files:** WhiteNoise
- **Documents and reports:** Pillow, openpyxl and ReportLab

## Django-only frontend policy

EduManage does not require npm, Node.js or a frontend build process. Production-ready CSS and JavaScript are committed under `static/` and served through Django and WhiteNoise.

A deployment therefore needs Python, the packages in `requirements.txt`, the database, migrations and static-file collection. There is no `npm install`, `npm ci` or frontend compilation step.

## Project structure

```text
edumanage-saas/
├── apps/
│   ├── public/          # Public-schema tenant, domain and platform-console code
│   └── tenant/          # School modules installed within tenant schemas
├── config/
│   ├── settings/
│   │   ├── base.py      # Common settings
│   │   ├── local.py     # Local SQLite development settings
│   │   ├── tenants.py   # django-tenants/PostgreSQL settings
│   │   └── prod.py      # Production hardening
│   ├── urls.py
│   ├── public_urls.py
│   ├── asgi.py
│   └── wsgi.py
├── docs/
├── static/
├── templates/
├── manage.py
├── requirements.txt
└── .env.example
```

## Requirements

- Python 3.11 or later
- pip and virtualenv
- PostgreSQL 13 or later for tenant and production deployments

## Local development

The default `manage.py` setup uses the local settings module and SQLite.

1. Clone the repository.

```bash
git clone https://github.com/birleopold/edumanage-saas.git
cd edumanage-saas
```

2. Create and activate a virtual environment.

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

3. Install Python dependencies.

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

4. Create the local environment file.

```bash
cp .env.example .env
```

5. Apply migrations and create an administrator.

```bash
python manage.py migrate
python manage.py createsuperuser
```

6. Start Django.

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000`.

## Tenant development with PostgreSQL

Use tenant mode when testing the SaaS architecture.

1. Configure PostgreSQL values in `.env`.

```env
POSTGRES_DB=edumanage_saas
POSTGRES_USER=postgres
POSTGRES_PASSWORD=replace-with-a-local-password
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
```

2. Select the tenant settings module.

```bash
export DJANGO_SETTINGS_MODULE=config.settings.tenants
```

On Windows PowerShell:

```powershell
$env:DJANGO_SETTINGS_MODULE="config.settings.tenants"
```

3. Apply public and tenant migrations.

```bash
python manage.py migrate_schemas --shared
python manage.py migrate_schemas
```

4. Create tenant and domain records through the platform console, Django admin or an approved management command.

### User isolation model

The custom user and campus-scope applications are installed in both schema groups:

- the **public schema** has platform-console users;
- every **school schema** has its own school users and role assignments.

The same username may therefore exist safely in separate school schemas without sharing account records.

## Production configuration

Production uses `config.settings.prod`, which imports tenant settings and applies strict security validation.

Start from `.env.production.example` and configure at least:

```env
DJANGO_SETTINGS_MODULE=config.settings.prod
DJANGO_SECRET_KEY=replace-with-at-least-50-random-characters
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=school.example.com,.school.example.com
DJANGO_TIME_ZONE=Africa/Kampala
ENVIRONMENT=production

POSTGRES_DB=edumanage_saas
POSTGRES_USER=edumanage
POSTGRES_PASSWORD=replace-with-a-strong-password
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432

ADMIN_2FA_REQUIRED=True
PAYMENT_CALLBACKS_ENABLED=False
MOBILE_MONEY_DRY_RUN_ENABLED=False
WEBHOOK_ALLOW_PRIVATE_TARGETS=False
WEBHOOK_ALLOW_HTTP=False
```

Production startup intentionally fails when important safeguards are missing or unsafe. This includes weak secrets, wildcard hosts, missing database credentials, disabled administrative 2FA requirements, mobile-money dry-run mode, or unsafe webhook settings.

### Payment-provider activation

Payment callbacks are disabled by default. Enable them only after configuring the real provider endpoint, credentials, subscription key and callback secret for MTN MoMo and/or Airtel Money.

A missing provider URL is never treated as a successful production payment request.

### Recommended infrastructure

- Gunicorn or another supported WSGI/ASGI server behind Nginx or an equivalent reverse proxy.
- PostgreSQL backups with tested restoration procedures.
- HTTPS certificates and renewal monitoring.
- Explicit `ALLOWED_HOSTS` and trusted proxy configuration.
- Secure media storage and access controls.
- Log rotation, error monitoring and alerting.
- Separate secret management for each environment.

## Security behaviour

- Payment callbacks fail closed when disabled, unsigned or missing provider secrets.
- Mobile-money callbacks validate provider, reference, amount and UGX currency.
- Production mobile-money dry runs are disabled.
- Campus query helpers return no rows for unassigned or unknown roles.
- Ambiguous duplicate-email authentication is rejected.
- Outbound webhook targets are checked at configuration and delivery time.
- Production webhooks require HTTPS and public network destinations unless explicitly allow-listed.
- Payment and invoice posting does not silently ignore accounting failures.
- Authenticated pages and attendance screens are not cached by the service worker.
- Offline attendance drafts use IndexedDB rather than ordinary localStorage.
- Attendance drafts are namespaced by tenant and signed-in session, expire automatically and are cleared during sign-out.
- Offline attendance replay uses idempotency keys and server-side response caching.

## Quality gates

Run the same important checks used by CI:

```bash
python manage.py check_dependency_lifecycle --strict
python manage.py check_release_gates --strict
python manage.py check_access_control_evidence --strict
python manage.py makemigrations --check --dry-run
python manage.py check
DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py check --deploy
python verify_routes.py
python manage.py test
pip-audit -r requirements.txt
```

Tenant validation requires PostgreSQL:

```bash
python manage.py migrate_schemas --shared --noinput --settings=config.settings.tenants
python manage.py check_tenant_isolation --strict --settings=config.settings.tenants
```

The tenant-isolation probe creates two temporary schemas, writes an overlapping username into both, verifies that the records remain separate and removes the schemas afterward.

CI does not install npm or run a Node-based asset build.

## Static files

Collect committed Django static assets before production deployment:

```bash
python manage.py collectstatic --noinput
```

WhiteNoise serves the collected files unless the deployment routes them through a dedicated static-file service.

## Useful commands

```bash
# Create migrations
python manage.py makemigrations

# Apply local migrations
python manage.py migrate

# Apply all tenant migrations
DJANGO_SETTINGS_MODULE=config.settings.tenants python manage.py migrate_schemas

# Create a superuser
python manage.py createsuperuser

# Run the development server
python manage.py runserver

# Run tests
python manage.py test
```

## User roles

- **Platform superuser:** SaaS tenant, domain and subscription management.
- **School administrator:** Full school administration and organisation setup.
- **Campus administrator:** Administration restricted to an assigned campus.
- **Teacher:** Course management, attendance, grading and class operations.
- **Student:** Schedules, grades, assignments and academic information.
- **Parent:** Learner progress, attendance, invoices and notices.

## API

API routes are mounted under:

```text
/api/v1/
```

The default REST framework policy requires authenticated sessions unless an endpoint explicitly defines another permission policy.

## Environment variables

See `.env.example` for local values and `.env.production.example` for production settings. Never commit real credentials or callback secrets.

## Contributing

1. Create a focused feature branch.
2. Keep changes small enough to review.
3. Add or update tests for changed behaviour.
4. Run the Django checks and test suite.
5. Open a pull request with deployment and security notes where relevant.

## License

This project is proprietary software. All rights reserved. Confirm repository visibility and distribution permissions before sharing source code or deployment artefacts.

## Changelog

### Production-hardening update

- Retained a Django-only frontend with committed static assets.
- Added strict payment, webhook, campus-scope and authentication safeguards.
- Added PostgreSQL shared-schema migration and tenant-isolation CI checks.
- Added Python dependency auditing and migration-drift enforcement.
- Improved private-page and offline-attendance handling.

### Version 1.0.0

- Initial school-management modules.
- Multi-tenant architecture foundation.
- Role-based access control.
- Template-based portal UI.
- Date-format placeholders across forms.
- Logo upload and branding support.
