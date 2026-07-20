# Education framework modernization

This programme modernizes EduManage for Ugandan institutions while keeping the platform internationally configurable. It follows a compatibility-first approach: existing modules remain the source of operational data until each phase has a tested migration and rollout path.

## Non-breaking rules

1. Existing models, records and URLs are not renamed or removed during the foundation phase.
2. New framework records are additive and tenant-scoped.
3. Existing `academics.Level` records are linked through `LevelStageMapping`; their names and IDs are not changed.
4. Administrator-confirmed level mappings are never overwritten by later automatic synchronization.
5. Existing grading scales are referenced by stored compatibility IDs until a later controlled migration can add direct framework relationships.
6. The setup interface is protected by the existing Academics feature flag and full-administrator permissions.
7. Every phase must pass migration drift checks, Django tests, production checks and PostgreSQL tenant-isolation tests before merging.

## Phase 1 foundation

The `education_frameworks` tenant app provides:

- `EducationStage` — ECD, Primary, Lower Secondary, Upper Secondary, Tertiary, University and Other;
- `AcademicFramework` — reusable curriculum and terminology templates;
- `FrameworkStage` — stage-specific class, subject, period and report labels;
- `InstitutionEducationProfile` — organization-level country, locale, institution type and framework settings;
- `CampusEducationStage` — campus-level stage, terminology, period, grading and report settings; and
- `LevelStageMapping` — a compatibility link to existing `academics.Level` records.

The migration seeds two templates:

- **Uganda National Curriculum** — neutral core labels plus Uganda aliases such as BOT, MOT, EOT, AOI, PLE, UCE, UACE, UNEB and MDD;
- **International or Custom Curriculum** — neutral terminology suitable for international and private curricula.

## Administrator setup screen

Open **Academics Setup → Education Framework** to:

- configure the institution type, country, locale and primary curriculum framework;
- choose local-and-international or international-neutral terminology;
- preview the labels users will see;
- map existing academic levels without renaming them;
- enable the stages used by each active campus;
- add or edit campus education stages;
- link stages to existing grading scales and report-layout keys;
- correct an automatic level classification manually; and
- view Phase 1 readiness and compatibility warnings.

The framework setup route is:

```text
/admin/academics/framework/
```

Only full administrators and Django superusers can change institution-wide framework settings. Campus administrators continue using normal academic workflows but cannot change the institution framework.

## Campus-aware stage assignment

Stage synchronization does not assume that every campus teaches every education stage.

- In a multi-campus institution, active `ClassGroup` records and their mapped levels determine the stages used by each campus.
- A primary-only campus therefore receives only Primary configuration, while a secondary campus receives only its secondary configuration.
- A new campus with no class-group evidence is left for explicit administrator assignment rather than receiving guessed stages.
- In a single-campus institution, all mapped stages are a safe fallback.
- Existing manually configured campus stages are preserved.

## Bootstrap command

Run inside a tenant schema using the normal tenant command workflow:

```bash
python manage.py bootstrap_education_frameworks \
  --map-levels \
  --enable-mapped-stages
```

Preview without changing data:

```bash
python manage.py bootstrap_education_frameworks \
  --map-levels \
  --enable-mapped-stages \
  --dry-run
```

For a new non-Ugandan profile:

```bash
python manage.py bootstrap_education_frameworks \
  --country-code KE \
  --locale en-KE \
  --institution-type MIXED \
  --map-levels
```

The command validates country and locale inputs. It is idempotent: it creates or refreshes system templates, creates the institution profile when missing, maps existing levels and optionally enables mapped stages. It never renames or deletes existing academic records. Existing profile choices should be changed through the administrator screen, not silently overwritten by the command.

## Read-only audit

Audit all tenant schemas without changing data:

```bash
python manage.py audit_education_frameworks
```

Audit one tenant and fail the command when setup is incomplete:

```bash
python manage.py audit_education_frameworks \
  --schema demo \
  --fail-on-incomplete
```

The audit checks:

1. the institution profile is active;
2. a primary framework is selected;
3. each campus has its inferred or explicitly assigned stages;
4. all existing levels are mapped;
5. no mapping references a deleted level;
6. grading-scale references are valid;
7. framework-stage links point to the selected framework;
8. framework-stage links match their campus stage; and
9. all configured stages are supported by the selected framework.

## Terminology resolution

New Python code should use `resolve_effective_terminology()` or `services.term()`. Both follow the same precedence and respect the local-terminology switch.

```python
from apps.tenant.education_frameworks.configuration import (
    resolve_effective_terminology,
)

labels = resolve_effective_terminology(
    profile=profile,
    campus_stage=campus_stage,
)
learner_label = labels["learner"]
```

Existing templates can adopt terminology gradually instead of being rewritten at once:

```django
{% load education_terms %}

<h1>{% education_term "learner" "Student" %} Results</h1>
<p>{% education_alias "EOT" "Final Examination" %}</p>
<p>{% education_alias "MDD" "Performing Arts" %}</p>
```

Resolution precedence is:

1. international-neutral defaults;
2. selected framework defaults when local terminology is enabled;
3. framework-stage defaults;
4. institution overrides;
5. an optional local campus-stage name; and
6. campus-stage overrides.

Explicit institution and campus overrides always take priority. When local terminology is disabled, framework-specific aliases and local stage names are not returned unless explicitly supplied as overrides.

Examples of configurable labels include:

- Student / Learner / Pupil
- Class / Grade / Year / Cohort
- Subject / Learning Area / Course Unit
- Term / Semester / Academic Period
- Report Card / Progress Report / Academic Transcript
- UNEB Exam / External Exam
- Boarding / Hostel / Residence
- Exam Clearance / Assessment Clearance

## Framework switching

Changing the primary framework relinks compatible campus stages while preserving local names, grading references, report-layout keys and other campus settings. If the new framework does not support a stage, only the old framework link is cleared. The campus stage and its local configuration remain intact for administrator review, and readiness remains incomplete until the unsupported stage is resolved.

## Phase 1 release gate

Before merging or deploying Phase 1:

```bash
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py check --deploy --settings=config.settings.prod
python verify_routes.py
python manage.py test
python manage.py migrate_schemas --shared --noinput --settings=config.settings.tenants
python manage.py check_tenant_isolation --strict --settings=config.settings.tenants
python manage.py audit_education_frameworks --fail-on-incomplete
```

Also run the repository dependency lifecycle, release-gate, access-control and `pip-audit` checks configured in `.github/workflows/ci.yml`.

## Rollout sequence

1. Back up the production database.
2. Deploy the code with the new additive tenant app.
3. Apply shared and tenant migrations using the established `django-tenants` deployment process.
4. Run the bootstrap command in dry-run mode for a representative tenant.
5. Run the bootstrap command for that tenant.
6. Review **Academics Setup → Education Framework** and correct any ambiguous mappings.
7. Run the strict audit for the tenant.
8. Repeat tenant by tenant after the pilot succeeds.

The Phase 1 migration only adds new framework tables and configuration. It does not rewrite existing academic, assessment, examination, coursework, finance or report data.

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
