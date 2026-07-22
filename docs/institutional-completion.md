# Institutional education completion layer

This layer completes the roadmap areas that require institution-specific configuration and auditable operational records without replacing the existing academics, assessment, examination, finance, boarding or activity sources of truth.

## Included capabilities

- ordered report-card templates and live PDF verification;
- structured ECD developmental observations;
- configurable generic, PLE, UCE, UACE and GPA result policies;
- academic transcripts with credit and grade-point support;
- learner-level subject-combination registration with capacity and campus checks;
- candidate photographs, document checklists, continuous-assessment readiness, mock cycles and subject attendance;
- verifiable candidate, clearance, gate, transcript and report documents;
- visitation windows, visitor identity, learner collection and return evidence;
- meal registers and campus-safe attendance;
- learner-property custody and release evidence;
- role-safe administrator, teacher, student and parent workflows.

## Rollout

```bash
python manage.py migrate_schemas --tenant --noinput --settings=config.settings.tenants
python manage.py audit_institutional_readiness --settings=config.settings.tenants
python manage.py collectstatic --noinput --settings=config.settings.tenants
```

Create at least one active default report template and result policy for each institution before enabling strict readiness checks.

## Validation

The release must pass migration drift, Django system and deployment checks, route verification, the complete automated test suite, dependency audit and PostgreSQL tenant-isolation proof before deployment.

## Safety

The migration is additive. Existing marks, reports, invoices, payments, examination results, bed allocations, activity memberships and learner profiles are not copied or rewritten.
