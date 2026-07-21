# Phase 7 operational hardening

This improvement extends the completed Phase 7 boarding and welfare consolidation with auditable guardian communications, welfare-case escalation and safe roll-call/leave reconciliation.

## Source-of-truth guarantees

The following records remain authoritative and are not copied or rewritten:

- `hostels.BedAllocation` for learner placement;
- `hostels.BoardingLeave` for leave workflow;
- `hostels.HostelRollCall` and explicit attendance decisions;
- `sickbay.SickbayVisit` for clinical records;
- `discipline.Incident` for discipline records;
- existing student, finance and report records.

The hardening layer adds only:

- `GuardianContactLog` for contact evidence;
- `WelfareCaseEscalation` for response deadlines and escalation state.

No SMS, WhatsApp, email or portal message is sent automatically.

## Guardian-contact evidence

Staff can record:

- purpose;
- method;
- outcome;
- contacted person and phone;
- notes;
- date/time;
- staff member;
- optional leave, welfare-case or roll-call-entry link.

A confirmed leave contact is evidence only. It does not change leave status, learner placement or a bed allocation.

## Welfare-case escalation

A welfare case may have one operational escalation record containing:

- escalation level;
- response deadline;
- escalation reason;
- guardian-contact requirement;
- escalating staff member and timestamp.

Each escalation also adds an ordinary welfare-case action so the existing case history remains complete.

## Safe roll-call reconciliation

Reconciliation compares draft roll calls with departed leave at the roll-call time.

It may only:

- change `UNMARKED` to `ON_LEAVE` and attach the correct leave record;
- change stale `ON_LEAVE` back to `UNMARKED` and clear the stale leave link.

It never overwrites `PRESENT`, `ABSENT`, `SICK` or `EXCUSED`.

Preview every tenant:

```bash
python manage.py reconcile_boarding_roll_calls
```

Preview one tenant:

```bash
python manage.py reconcile_boarding_roll_calls --schema demo
```

Apply reviewed safe changes:

```bash
python manage.py reconcile_boarding_roll_calls --schema demo --apply
```

Limit to one draft roll call:

```bash
python manage.py reconcile_boarding_roll_calls --schema demo --roll-call 42 --apply
```

## Audit

The existing Phase 7 audit now also reports:

- boarders missing primary guardian details;
- departed learners without confirmed guardian-contact evidence;
- overdue welfare-case response deadlines;
- unassigned high or critical cases;
- draft roll calls requiring reconciliation.

```bash
python manage.py audit_boarding_welfare --schema demo
python manage.py audit_boarding_welfare --schema demo --fail-on-incomplete
```

## Administrator routes

- Phase 7 dashboard: `/admin/hostels/welfare/`
- Operational safety: `/admin/hostels/welfare/operations/`
- Guardian evidence is added from leave and welfare-case detail pages.
- Draft roll calls expose a **Reconcile Leave** action.

## Rollback

Application rollback is safe because the new records are additive. Reverting the application restores the completed Phase 7 behavior. Contact logs and escalation records may remain unused until the migration is rolled back during a controlled maintenance window.
