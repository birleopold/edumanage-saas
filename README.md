# EduManage SaaS — School Management System

EduManage SaaS is a Django-based school management platform for administration, academic records, finance, communication, reporting and school operations. It supports PostgreSQL schema-based multi-tenancy through `django-tenants`, while retaining a simple SQLite development mode.

## Technology

- **Backend:** Django 5.2 LTS
- **Multi-tenancy:** django-tenants
- **Database:** SQLite for local development; PostgreSQL for SaaS and production
- **API:** Django REST Framework
- **Frontend:** Django templates and committed static CSS/JavaScript
- **Static files:** WhiteNoise
- **Documents and reports:** Pillow, openpyxl and ReportLab

## Django-only frontend policy

EduManage does not require npm, Node.js or a frontend build process. Production-ready CSS and JavaScript are committed under `static/` and served through Django/WhiteNoise. Clone, install Python requirements, migrate and run without npm.

## Requirements

- Python 3.11+
- pip and virtualenv
- PostgreSQL 13+ for tenant and production deployments

## Local development

```bash
git clone https://github.com/birleopold/edumanage-saas.git
cd edumanage-saas
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

On Windows:

```powershell
.venv\Scripts\activate
```

## Tenant development

```bash
export DJANGO_SETTINGS_MODULE=config.settings.tenants
python manage.py migrate_schemas --shared
python manage.py migrate_schemas
```

## Production

Copy `.env.production.example` into the production environment manager. Production startup intentionally fails when important safeguards are missing. Configure an explicit host list, a secret of at least 50 random characters, a PostgreSQL password, admin 2FA, disabled mobile-money dry run, and public HTTPS-only webhook destinations.

Payment callbacks remain disabled until a provider URL and callback secret are configured. Production never treats a missing provider URL as a successful payment request.

## Security behaviour

- Payment callbacks fail closed when disabled or missing secrets.
- Mobile-money callbacks verify provider network, reference, amount and currency.
- Campus query helpers return no rows for unassigned or unknown roles.
- Authenticated pages are not cached by the service worker.
- Offline attendance drafts are isolated and cleared during logout.
- Production webhooks must use HTTPS and public network destinations.
- Ambiguous duplicate emails cannot authenticate.
- Payment and invoice changes enforce accounting posting safeguards.

## Quality gates

```bash
python manage.py check_dependency_lifecycle --strict
python manage.py check
python manage.py makemigrations --check --dry-run
DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py check --deploy
python verify_routes.py
python manage.py test
pip-audit -r requirements.txt
```

CI also runs tenant tests against PostgreSQL schemas and does not install npm.

## License

This project is proprietary software. All rights reserved. Confirm repository visibility matches the intended licensing and distribution policy.
