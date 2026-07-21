# Phase 9 — Fees and assessment-clearance rules

Phase 9 adds an optional finance-policy layer around existing assessment and examination access.

## Source-of-truth guarantees

- `finance.Invoice`, invoice lines, adjustments and `finance.Payment` remain authoritative.
- Assessment scores, examination scores, online attempts, report cards, enrollments and learners are not copied or rewritten.
- No matching active valid policy means access remains allowed.
- Inactive or invalid policies never block access.
- Advisory policies show a warning and continue.
- Blocking policies affect only the configured access surface.
- Overrides are explicit, time-limited, reasoned and approved records.

## Controlled access surfaces

- online examination start and take routes;
- student and parent assessment results;
- student and parent assessment report cards;
- student and parent examination results;
- student and parent examination report-card PDFs.

Exam schedules and ordinary dashboards remain available.

## Policy rules

Policies support:

- full payment;
- minimum paid percentage;
- maximum outstanding balance;
- current/matching academic-term invoices;
- all active invoices;
- institution, campus, education-stage, level, programme and academic-term scope;
- deterministic resolution by priority and scope specificity;
- advisory or blocking enforcement.

## Safe bootstrap

The bootstrap command is dry-run by default and creates inactive templates only.

```bash
python manage.py bootstrap_clearance_policies --schema demo
python manage.py bootstrap_clearance_policies --schema demo --apply
```

Inactive templates cannot block access. Administrators must review scope, thresholds, messages and enforcement before activation.

## Read-only audit

```bash
python manage.py audit_clearance_policies --schema demo
python manage.py audit_clearance_policies --schema demo --fail-on-incomplete
```

The audit reports policy counts, invalid policies, expired active overrides, missing access-type configuration and decision-log counts. Missing access types are informational because those routes remain open.

## Administrator routes

```text
/admin/finance/clearance/
/admin/finance/clearance/check/
```

Only full tenant administrators can configure policies, approve overrides and record decision snapshots.

## Rollout sequence

1. Deploy migrations.
2. Run the dry-run bootstrap.
3. Create inactive templates with `--apply`.
4. Configure and test policies using the learner-check page.
5. Begin with advisory enforcement.
6. Review finance allocations and exceptions.
7. Change selected policies to blocking only after institutional approval.
8. Run the strict audit.

## Rollback

Deactivate all clearance policies. Access immediately returns to the pre-Phase-9 default because the evaluator allows access when no active valid policy matches. Existing invoices, payments, scores, attempts and reports require no rollback.
