# EduManage Roadmap Gap-Closure Plan

This plan closes the remaining Phase 1–9 gaps without resetting, rebasing, force-pushing, or replacing `origin/main`. Every change is additive or backwards-compatible, is delivered as a normal commit on `main`, and must preserve tenant isolation and existing records.

## Delivery rules

1. Keep `main` as the active integration branch.
2. Never rewrite published history.
3. Use additive migrations first; remove legacy fields only in a later cleanup release.
4. Run Django checks, migration-drift checks, the complete test suite, dependency audit, production checks, route checks, PostgreSQL shared migrations, and tenant-isolation proof before marking a phase complete.
5. Add a readiness/audit command for every new configuration area.
6. Keep old records readable while new rules are introduced.
7. Use one authoritative service for each result, clearance, permit, and learner-record calculation.

## Phase 1 — Institution, curriculum, stages, and terminology

### Objective
Make academic-stage configuration strongly typed and safely validated.

### Steps
1. Replace the loose grading-scale numeric reference with a real foreign key while preserving the legacy identifier during migration.
2. Add explicit, validated stage configuration for:
   - report presentation mode;
   - candidate-class behaviour;
   - numeric versus competency-based default assessment mode;
   - whether stage results support promotion decisions.
3. Keep `candidate_settings` and general `settings` for future extensions, but move current business-critical flags into dedicated fields.
4. Update administrator forms, dashboards, and Django admin.
5. Add migration tests and model validation tests.
6. Extend framework readiness checks to detect missing or inactive grading-scale links.

### Completion gate
Every active campus stage has a valid institution, framework stage, period type, grading-scale relationship where required, and validated reporting/candidate defaults.

## Phase 2 — Assessments and examinations

### Objective
Represent all assessment policies explicitly and consistently.

### Steps
1. Add assessment grading mode: numeric, competency, or mixed.
2. Add explicit report-card visibility separate from portal publication.
3. Add absent-learner policy: missing, zero, excused, deferred, or makeup required.
4. Add makeup/deferred assessment support.
5. Add competency result fields and optional competency framework links.
6. Ensure assessment and examination-paper sources use the same classification and weighting resolver.
7. Add administrator forms, teacher workflows, audit checks, and regression tests.

### Completion gate
Every published result has an explicit grading mode, absence policy, report-card policy, and deterministic contribution to the selected weighting scheme.

## Phase 3 — Coursework and learning activities

### Objective
Make requested learning-activity types and submission states first-class.

### Steps
1. Add first-class activity kinds for classwork, weekend work, essays, laboratory reports, fieldwork, group assignments, reading exercises, research work, and activity of integration.
2. Add group definitions, group membership, and group submission ownership.
3. Add submission states: draft, submitted, late, excused late, returned, resubmission requested, resubmitted, marked.
4. Store late status at submission time while retaining a computed consistency check.
5. Add competency-achievement fields and links to Phase 2 assessment components.
6. Add teacher marking, resubmission, and learner progress workflows.
7. Add migration/bootstrap logic for existing materials and assignments.

### Completion gate
Every activity can be classified, assigned, submitted, marked, audited, and reported without relying on title inference.

## Phase 4 — Grading, report cards, transcripts, and academic history

### Objective
Use one authoritative result pipeline everywhere.

### Steps
1. Introduce a single result facade used by student, parent, administrator, PDF, transcript, and verification routes.
2. Remove independent simple-average calculations from institutional document generation.
3. Resolve weighting scheme, grading profile, result policy, and report template in one ordered pipeline.
4. Ensure PLE, UCE, UACE, GPA, and competency summaries consume the same course results.
5. Add tertiary/university registration and attempt records:
   - semester registration;
   - ordinary, retake, supplementary, and repeat attempts;
   - replacement rules;
   - semester GPA and CGPA;
   - academic standing;
   - transcript attempt history.
6. Version generated reports and transcripts so verification refers to the issued snapshot.
7. Add cross-output parity tests proving HTML and PDF results match.

### Completion gate
The same learner, period, and data produce identical grades and summaries in every portal and document.

## Phase 5 — Programme pathways and subject combinations

### Objective
Complete Uganda A-Level semantics and international pathway flexibility.

### Steps
1. Extend subject roles with principal, subsidiary, compulsory, general paper, subsidiary ICT, and subsidiary mathematics.
2. Add a dedicated combination capacity field.
3. Validate minimum/maximum principal and subsidiary counts.
4. Use registered subject roles—not best scores—to calculate UACE points.
5. Add learner combination history and controlled changes within an academic year.
6. Integrate combinations into offering planning, candidate registration, and result calculation.
7. Add pathway and combination readiness checks.

### Completion gate
UACE and equivalent programme results are derived from the learner’s approved registered combination and role structure.

## Phase 6 — Candidates and external examinations

### Objective
Connect candidate readiness, registration, continuous assessment, and finance clearance.

### Steps
1. Add candidate-clearance access types to Phase 9.
2. Add a candidate readiness service that checks photograph, documents, continuous assessment, subject registration, centre/session dates, and finance clearance.
3. Prevent `READY`, `SUBMITTED`, and `APPROVED` transitions when blocking conditions remain.
4. Add explicit authorised overrides with reason, approver, validity, and evidence.
5. Generate candidate permits from approved dossiers.
6. Keep import/export and official result records linked to the candidate dossier.
7. Add transition and audit tests.

### Completion gate
No candidate can be submitted or approved without a reproducible readiness decision or authorised override.

## Phase 7 — Boarding and welfare

### Objective
Complete house/residence staffing and operational duty management.

### Steps
1. Add school houses separately from hostels.
2. Add boarding/house staff assignments with roles: house master, house mistress, matron, warden, patron, and duty staff.
3. Add assignment start/end dates and campus/house/hostel scope.
4. Integrate staff assignments with leave approval, roll calls, welfare escalation, visitor handover, and gate passes.
5. Add duty rosters and escalation deadlines.
6. Add role-scoped dashboards and audit reports.
7. Add safeguarding access tests.

### Completion gate
Every boarding and house operation has a responsible authorised staff assignment and auditable handover path.

## Phase 8 — Clubs, sports, and co-curricular life

### Objective
Finish learner-, parent-, teacher-, and patron-facing delivery.

### Steps
1. Add teacher/patron programme-management permissions and navigation.
2. Add student activities, attendance, consent, medical clearance, roles, and achievements pages.
3. Add parent participation and consent views.
4. Add activity-specific discipline/incident links.
5. Add report-card co-curricular comments and participation summaries.
6. Add printable, verifiable certificates generated from achievement records.
7. Add participation and certificate parity tests.

### Completion gate
Authorised staff can manage activities, and learners/parents can see accurate participation and verified achievements.

## Phase 9 — Fees, clearance, exceptions, and permits

### Objective
Complete the policy-to-decision-to-permit lifecycle.

### Steps
1. Add minimum-paid-amount rule.
2. Add access types for physical exam attendance, candidate registration, external submission, and permit issuance.
3. Add typed exception categories: scholarship, sponsorship, bursary, payment plan, special arrangement, and manual bursar approval.
4. Add evidence/reference fields and approval limits.
5. Generate a versioned verifiable permit from a successful or overridden decision.
6. Store policy, financial snapshot, decision, override, approver, validity, and QR verification reference on the issued permit.
7. Revoke or expire permits when the underlying decision is invalidated, while preserving history.
8. Add finance, candidate, portal, and document integration tests.

### Completion gate
Every protected action can produce a traceable decision and, where configured, a verifiable permit whose contents match the decision snapshot.

## Final release gate

The roadmap is considered fully realised only when:

- all nine phase readiness checks pass for every active tenant;
- no migration drift exists;
- all role and campus isolation tests pass;
- report and transcript parity tests pass;
- candidate and clearance transition tests pass;
- issued permits verify against immutable decision snapshots;
- complete CI passes on PostgreSQL and production settings.
