# Dependency lifecycle

EduManage treats framework support windows as release gates, not background chores. The supported platform is deliberately Django-only:

- **Django:** `5.2.x` LTS, supported until **April 2028**.
- **Tenant middleware:** `django-tenants>=3.10.2`.
- **Python:** CI pins `3.11`.
- **Frontend assets:** committed Django static files; no npm, Node runtime, or frontend build step is required.

## Monthly dependency review

Run this review during the first release window of each month:

```bash
python manage.py check_dependency_lifecycle --strict
python -m pip list --outdated
pip-audit -r requirements.txt
```

For each proposed framework or security update:

1. Read release notes for Django, django-tenants, Django REST Framework, Simple JWT, WhiteNoise, Pillow, psycopg, ReportLab and packages with security advisories.
2. Create a focused upgrade branch.
3. Run the release gates locally and in CI.
4. Record release-note links and test results in the pull request.

## Required gates

```bash
python manage.py check_dependency_lifecycle --strict
python manage.py check
DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python verify_routes.py
python manage.py test
pip-audit -r requirements.txt
```

Production upgrades must also run tenant tests against PostgreSQL schemas. Generated CSS and JavaScript are committed under `static/`; no npm command is part of installation or deployment.
