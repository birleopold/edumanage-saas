# Transport notices and integrity controls

This change replaces the stale transport schedules and notifications pull request with an implementation based on the current `main` branch.

## Admin routes

- `/admin/transport/schedules/`
- `/admin/transport/notices/`
- `/admin/transport/notices/create/`

Transport notice lists and form choices are restricted to the signed-in campus administrator's assigned campus. Global school administrators retain school-wide access.

## Parent and student routes

- `/parent/transport/assignments/<id>/`
- `/student/transport/assignments/<id>/`

Parent access is restricted to students connected through `ParentStudentLink`. Student access is restricted to the signed-in student's own assignments. Detail pages show the route, stop, vehicle, driver, active schedules, latest tracking record and, for parents, the notice history.

## Tenant integrity audit

The existing command now includes transport checks:

```bash
python manage.py audit_tenant_integrity --schema demo
python manage.py audit_tenant_integrity --schema demo --fail-on-errors
```

Transport findings cover:

- multiple active assignments for one student;
- stop and route mismatches;
- active assignments on inactive routes or stops;
- assignments left active after their end date;
- vehicle capacity overruns; and
- tracking records linked to the wrong route vehicle.

The audit remains read-only and does not modify tenant data.
