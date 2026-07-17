# Access-control evidence

Phase 2 is cleared by automated tests and a CI gate, not by manual review alone.

## CI gate

```bash
python manage.py check_access_control_evidence --strict
```

The command verifies:

- role-gate primitives in `apps/tenant/portals/permissions.py`;
- campus scope helpers in `apps/tenant/portals/campus_permissions.py`;
- PostgreSQL tenant schema context in public tenant onboarding;
- production tenant readiness documentation that requires PostgreSQL schemas;
- module-level campus-scope tests for finance, assessments, attendance, sickbay, students, parents, HR/payroll, analytics, reports, library, hostels, transport, teachers and coursework self-service.

## Test evidence highlights

- Campus-admin list, detail, create, edit, export and mutation tests exist across sensitive modules.
- Parent, student and teacher self-service tests cover forced browsing attempts against another user or unrelated coursework/student records.
- Tenant status middleware blocks suspended and archived tenant schemas while leaving public health/platform routes available.
- Tenant onboarding uses `tenant_context` only when PostgreSQL tenancy is active, keeping local SQLite previews honest while production remains schema-aware.

Keep this document and `check_access_control_evidence` updated whenever a new sensitive module or self-service route is added.
