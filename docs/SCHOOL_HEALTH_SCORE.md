# School Setup Health Score

The School Setup Health Score is an admin readiness dashboard for confirming whether a tenant school is operationally ready.

## Where To Find It

- Admin page: `/admin/school-health/`
- JSON endpoint: `/admin/school-health/data/`
- Command center summary: `/admin/`
- System status summary: `/admin/system-status/`
- CLI command: `python manage.py check_school_health`

## Scored Categories

The score is weighted to 100 points:

- Campuses configured: 15 points
- Academic terms active: 15 points
- Fee structures set: 15 points
- Roles assigned: 15 points
- PWA alerts ready: 15 points
- Backups enabled: 10 points
- Payment connectors configured: 15 points

Each category reports evidence, missing points, and a next action.

## CLI Usage

Print a text report:

```bash
python manage.py check_school_health
```

Print the complete JSON payload:

```bash
python manage.py check_school_health --json
```

Fail a deployment or scheduled check below a minimum score:

```bash
python manage.py check_school_health --min-percent 85
```

Include ready categories in the text report:

```bash
python manage.py check_school_health --show-complete
```

## Notes

Payment connector readiness checks active MTN MoMo or Airtel Money integration provider rows first, then falls back to runtime payment settings.

PWA alert readiness checks VAPID keys and active browser push subscriptions.

Backup readiness checks for a successful or restore-tested backup in the last 14 days.
