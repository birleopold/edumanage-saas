# Education framework modernization

This programme modernizes EduManage for Ugandan institutions while keeping the platform internationally configurable. It follows a compatibility-first approach: existing modules remain the source of operational data until each phase has a tested migration and rollout path.

## Non-breaking rules

1. Existing models, records and URLs are not renamed or removed during the foundation phase.
2. New framework records are additive and tenant-scoped.
3. Existing `academics.Level` records are linked through `LevelStageMapping`; their names and IDs are not changed.
4. Existing grading scales are referenced by stored compatibility IDs until a later controlled migration can add direct framework relationships.
5. New user-interface behaviour will be introduced behind feature flags.
6. Every phase must pass migration drift checks, Django tests, production checks and PostgreSQL tenant-isolation tests before merging.

## Phase 1 foundation

The `education_frameworks` tenant app provides:

- `EducationStage` — ECD, Primary, Lower Secondary, Upper Secondary, Tertiary, University and Other;
- `AcademicFramework` — reusable curriculum and terminology templates;
- `FrameworkStage` — stage-specific class, subject, period and report labels;
- `InstitutionEducationProfile` — organization-level country, locale, institution type and framework settings;
- `CampusEducationStage` — campus-level stage, terminology, period, grading and report settings;
- `LevelStageMapping` — a compatibility link to existing `academics.Level` records.

The migration seeds two templates:

- **Uganda National Curriculum** — neutral core labels plus Uganda aliases such as BOT, MOT, EOT, AOI, PLE, UCE, UACE, UNEB and MDD;
- **International or Custom Curriculum** — neutral terminology suitable for international and private curricula.

## Bootstrap command

Run inside a tenant schema using the normal tenant command workflow:

```bash
python manage.py bootstrap_education_frameworks --map-levels --enable-mapped-stages
```

Preview without changing data:

```bash
python manage.py bootstrap_education_frameworks --map-levels --enable-mapped-stages --dry-run
```

For a non-Ugandan institution:

```bash
python manage.py bootstrap_education_frameworks \
  --country-code KE \
  --locale en-KE \
  --institution-type MIXED \
  --map-levels
```

The command is idempotent. It creates or refreshes system templates, creates the institution profile when missing, maps existing levels and optionally enables mapped stages for active campuses. It never renames or deletes existing academic records.

## Terminology resolution

Application code should use `education_frameworks.services.term()` instead of hard-coding market-specific labels in new screens.

```python
from apps.tenant.education_frameworks.services import term

label = term("learner", profile=profile, campus_stage=campus_stage)
```

Resolution follows this concept:

1. international-neutral defaults;
2. selected framework defaults;
3. institution terminology;
4. stage terminology;
5. campus-stage overrides.

Examples of configurable labels include:

- Student / Learner / Pupil
- Class / Grade / Year / Cohort
- Subject / Learning Area / Course Unit
- Term / Semester / Academic Period
- Report Card / Progress Report / Academic Transcript
- UNEB Exam / External Exam
- Boarding / Hostel / Residence
- Exam Clearance / Assessment Clearance

## Fusion plan for phases 2–10

### Phase 2 — Assessments and examinations

Extend the existing `assessments.Assessment`, `exams.Exam` and `exams.ExamPaper` flows with shared assessment-type and weighting profiles. Do not create a second marks table.

### Phase 3 — Coursework and learning activities

Make the existing `coursework.Assignment`, `LearningMaterial` and submission models the common learning-activity engine. Add activity categories and assessment links instead of creating separate homework, project and AOI tables.

### Phase 4 — Grading and reports

Extend existing `academics.GradingScale`, grading services and report services with framework/stage applicability, competency descriptors, aggregates, divisions, GPA and CGPA policies.

### Phase 5 — Subject combinations

Build subject combinations and programme pathways around existing `Course`, `CourseOffering`, `Program`, `Enrollment` and student records.

### Phase 6 — Candidates and external examinations

Extend existing exams and student records with examination bodies, centre numbers, candidate registrations, continuous-assessment completeness and mock cycles.

### Phase 7 — Boarding and welfare

Consolidate the current hostels, sickbay, discipline, duty, attendance and student modules through shared welfare workflows and student movement records.

### Phase 8 — Clubs, sports and activities

Expand the current activities module into the common co-curricular engine; do not create separate systems for sports, MDD, debate and clubs.

### Phase 9 — Fees and clearance

Build configurable clearance policies on top of existing finance balances, payments and audit records. Clearance must support percentages, fixed amounts, bursar approval, scholarships and overrides.

### Phase 10 — Reports and rollout

Add the report-card builder, terminology-aware navigation, compatibility migrations, feature flags, audit checks and tenant-by-tenant rollout tools.
