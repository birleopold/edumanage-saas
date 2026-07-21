# Phase 8 — Clubs, sports and co-curricular consolidation

Phase 8 adds an operational layer around the existing `Activity` and `ActivityMember` records.

## Source-of-truth guarantees

The following existing records remain authoritative and are not copied or rewritten:

- activities and activity types;
- learner activity memberships;
- students, streams and campuses;
- activity heads and staff profiles;
- finance, invoices, receipts and balances;
- academic results and report cards.

## Additive capabilities

- one programme profile per activity;
- open, selective or team-based participation;
- optional capacity, attendance, guardian-consent and medical-clearance rules;
- teams, squads, ensembles, committees and houses;
- participation roles and safeguards per existing membership;
- meetings, training, matches, competitions, performances, service and trips;
- deliberate attendance registers generated from active memberships;
- learner leadership, participation, award, medal, certificate, record and service achievements.

Attendance always starts as `UNMARKED`. Completing an attendance-required session is blocked until every participant has been deliberately marked.

## Rollout

Preview programme and participation profile creation:

```bash
python manage.py bootstrap_activity_programmes --schema demo
```

Apply the additive setup:

```bash
python manage.py bootstrap_activity_programmes --schema demo --apply
```

Run the read-only audit:

```bash
python manage.py audit_activity_programmes --schema demo
```

After configuration is complete:

```bash
python manage.py audit_activity_programmes --schema demo --fail-on-incomplete
```

## Administrator routes

```text
/admin/activities/
/admin/activities/programme/
/admin/activities/programme/sessions/
```

## Rollback

Application rollback restores the existing activities and memberships interface. The additive Phase 8 tables may remain unused until a controlled migration rollback. Existing activities, memberships, learners, staff and finance records are unaffected.
