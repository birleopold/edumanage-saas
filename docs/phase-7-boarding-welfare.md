# Phase 7 — Boarding and student welfare consolidation

Phase 7 adds a coordination layer around EduManage's existing hostel, sickbay and discipline records.

## Authoritative records

The following remain the source of truth and are not copied or rewritten:

- `hostels.Hostel`, `HostelRoom` and `Bed` for accommodation inventory;
- `hostels.BedAllocation` for current and historical learner placement;
- `sickbay.StudentMedicalProfile` and `SickbayVisit` for medical information;
- `discipline.Incident` and `IncidentAction` for disciplinary records;
- existing student, finance, parent and report routes.

Phase 7 welfare cases may reference a bed allocation, sickbay visit or discipline incident, but do not duplicate the clinical or disciplinary record.

## New capabilities

- learner boarding profiles with day/full/weekly/flexible status;
- guardian, pickup, dietary, accessibility and safeguarding notes;
- approved leave with explicit approval, departure, guardian handover and return transitions;
- hostel roll calls generated from active bed allocations;
- roll-call entries that default to **Not marked**, never automatically to present;
- welfare cases with category, severity, confidentiality, ownership, follow-up and resolution;
- student welfare timelines combining references to existing boarding, health, discipline, leave and welfare records;
- structural readiness and operational-alert reporting.

## Safe profile bootstrap

The command is a dry run unless `--apply` is supplied:

```bash
python manage.py bootstrap_boarding_profiles --schema demo
```

Apply the reviewed profile creation:

```bash
python manage.py bootstrap_boarding_profiles --schema demo --apply
```

The initial status is derived from current records:

- an active `BedAllocation` creates a full-boarder profile;
- no active allocation creates a day-learner profile.

The command does not create or end bed allocations, change learner placement, create health/discipline records, or post finance transactions.

## Audit

Read-only audit:

```bash
python manage.py audit_boarding_welfare --schema demo
```

Strict deployment/readiness gate:

```bash
python manage.py audit_boarding_welfare --schema demo --fail-on-incomplete
```

Structural readiness checks:

- every active learner has a boarding profile;
- active allocations and boarder profile statuses agree;
- completed or locked roll calls have no unmarked entries.

Operational alerts are reported separately and do not make migration unsafe:

- overdue departed leave;
- open welfare cases;
- unresolved critical welfare cases.

## Access control

- full administrators and superusers manage institution-wide profile setup and readiness;
- campus administrators use existing campus-scoped learner, leave and welfare-case views;
- confidential welfare cases are hidden from campus administrators unless they opened or own the case;
- existing hostel inventory permissions remain unchanged.

## Rollout

1. Apply shared and tenant migrations.
2. Run the profile bootstrap as a dry run.
3. Apply profile creation after reviewing counts.
4. Review boarder profiles that do not have active allocations.
5. Review active allocations whose learners are not marked as boarders.
6. Start leave and roll-call workflows per hostel.
7. Use welfare cases only as coordination records; continue recording medical and discipline details in their existing modules.
8. Run the strict audit when structural setup is complete.

## Rollback

Application rollback is safe because Phase 7 does not replace existing hostel, sickbay or discipline data. Existing modules continue to operate if the new routes are unused. The additive Phase 7 tables may remain dormant until a controlled migration rollback is approved.
