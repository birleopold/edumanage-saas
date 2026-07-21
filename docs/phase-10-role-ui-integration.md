# Phase 10 — Phase 1–9 role UI integration

## Purpose

This Phase 10 hardening pass makes the capabilities delivered in Phases 1–9 discoverable from the correct user interface without replacing their original models, services, routes or permission checks.

## Shared capability catalogue

`apps/tenant/portals/capability_catalog.py` is the single presentation catalogue for the completed phases. It records:

1. institution, curriculum and terminology profiles;
2. configurable assessment types and weighting schemes;
3. unified learning activities;
4. grading profiles and report rules;
5. programme pathways and subject combinations;
6. candidate and external examination management;
7. boarding and learner welfare;
8. clubs, sports and co-curricular participation;
9. fee and assessment-clearance rules.

The catalogue contains presentation metadata and named-route links only. It does not calculate grades, change pathways, register candidates, update welfare cases, record attendance, create invoices or make clearance decisions.

## Role-specific pages

- `/admin/capabilities/`
- `/teacher/capabilities/`
- `/student/capabilities/`
- `/parent/capabilities/`

Full administrators receive configuration and readiness links. Campus administrators receive only campus-scoped or operational links already permitted by the existing views. Teachers receive teaching, assessment, examination and learner-support workflows. Students and parents receive existing learning, results, exam, boarding and finance routes.

When a phase has no direct action for a role, the interface explains that the feature is managed by authorised school staff and applied automatically. It never renders a broken or unauthorised configuration link.

## Portal navigation

The standard portal shell loads `phase-capability-nav.js` and `phase-capability-nav.css`. The script reads the existing body role class and inserts one accessible capability-centre link into the sidebar. It does not alter authentication, route resolution or the underlying sidebar permissions.

## Non-breaking guarantees

- Existing Phase 1–9 routes remain unchanged.
- Existing role decorators and campus scoping remain authoritative.
- No academic, finance, candidate, boarding, welfare, activity, enrollment or learner record is copied or rewritten.
- Route names are reversed at runtime; unavailable routes are omitted rather than guessed.
- Campus administrators never receive full-administrator configuration links from the catalogue.
- Teachers, students and parents never receive administrative configuration links.

## Validation

The Phase 10 regression tests verify:

- exactly nine completed phases are shown;
- full administrators receive all configuration entry points;
- campus administrators receive operational links but not institution-wide configuration links;
- teachers receive teaching, assessment and exam links;
- students receive coursework, results, exam, boarding and finance links;
- parents receive child-facing coursework, results, exam, boarding and finance links;
- cross-role access remains forbidden;
- every rendered action resolves to an existing named route.

Before deployment, run the normal migration-drift, Django, route, full-test, dependency-audit and PostgreSQL tenant-isolation gates. No new database migration is expected for this UI-only integration.
