# Dependency lifecycle

EduManage treats framework support windows as release gates, not background chores. The current supported framework target is:

- **Django:** `5.2.x` LTS, supported by Django until **April 2028**.
- **Tenant middleware:** `django-tenants>=3.10.2`, because the older `3.6.1` pin declared `Django<5.1`.
- **Python:** CI pins `3.11`.
- **Node:** CI pins `20`.

## Monthly dependency review

Run this review during the first release window of each month:

```bash
python manage.py check_dependency_lifecycle --strict
python -m pip list --outdated
npm outdated
npm audit --omit=dev
```

For each proposed framework or security update:

1. Read the release notes for Django, django-tenants, Django REST Framework, Simple JWT, WhiteNoise, Pillow, psycopg, and any package with a security advisory.
2. Create a short upgrade branch that changes only dependency pins and compatibility fixes.
3. Run the release gates below locally and in CI.
4. Record the release-note links and test results in the pull request or release notes.

## Django LTS upgrade path

The 4.2 LTS line reached the end of extended support on April 7, 2026. The tested replacement path is:

```txt
Django==5.2.16
django-tenants==3.10.2
```

The first install attempt exposed the key compatibility constraint: `django-tenants==3.6.1` is not compatible with Django 5.2 because it declares `Django<5.1`. Upgrade `django-tenants` with Django.

## Required gates

```bash
python manage.py check_dependency_lifecycle --strict
python manage.py check
DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py check --deploy
python verify_routes.py
python manage.py test
npm audit --omit=dev
```

Production upgrades must also run tenant migration smoke tests against PostgreSQL schemas before customer rollout.
