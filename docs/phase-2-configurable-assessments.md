# Phase 2 — Configurable assessment types and weighting schemes

## Purpose

Phase 2 adds a configurable result-policy layer without replacing the existing classroom assessment, examination or score-entry systems. `assessments.AssessmentScore` and `exams.ExamScore` remain the operational sources of marks.

## Non-breaking guarantees

- Existing `Assessment`, `AssessmentScore`, `Exam`, `ExamPaper` and `ExamScore` records remain valid.
- Existing assessment and exam-paper `weight` fields remain supported as the legacy fallback.
- New assessment-type and weighting-component links are nullable.
- No migration copies, recalculates or deletes existing marks.
- Configurable aggregation reads classroom scores and examination scores directly from their existing tables.
- Optional exam-paper compatibility links create metadata-only `Assessment` records; they do not copy `ExamScore` rows.

## Configuration models

### AssessmentType

Reusable categories include Quiz, Test, Assignment, Project, Practical, Coursework, Oral/Presentation, Examination, BOT, MOT, EOT and AOI. Each category supports a neutral name, an international kind and optional country aliases.

### AssessmentWeightingScheme

A scheme may apply globally or be narrowed by campus, education stage, academic term and programme. The resolver chooses the highest-priority, most-specific valid scheme. Invalid schemes are never used.

Missing-score policies:

- `INCOMPLETE`: a required component below its minimum occurrence count prevents a final result.
- `ZERO`: a missing required component contributes zero.
- `IGNORE`: completed component weights are normalised when permitted.

### AssessmentWeightingComponent

Each component defines an assessment type, contribution weight, average/best/latest aggregation, minimum and maximum occurrences, optional dropped-lowest scores, required/optional status and display order.

Active component weights must equal the scheme total before the scheme can resolve.

## Result calculation

For a student and course offering:

1. Resolve the valid scheme from campus, stage, term and programme.
2. For each component, read matching `AssessmentScore` and `ExamScore` records.
3. Convert each score to a percentage using its own maximum score.
4. Apply occurrence limits, dropped-lowest rules and average/best/latest aggregation.
5. Apply the scheme's missing-score policy.
6. Calculate the final weighted percentage without modifying source marks.
7. Fall back to existing assessment weights and simple averages when no valid scheme applies.

## Administrator workflow

Open **Assessments → Framework** to:

- review readiness and invalid-scheme warnings;
- manage assessment types and local aliases;
- create scoped weighting schemes;
- add and validate components;
- classify existing assessments and exam papers safely.

Campus administrators cannot change institution-wide assessment framework settings. Full administrators and superusers can manage them.

## Commands

Preview or apply template/classification changes:

```bash
python manage.py bootstrap_assessment_frameworks --schema demo --classify-existing --dry-run
python manage.py bootstrap_assessment_frameworks --schema demo --classify-existing
```

Create optional metadata-only exam-paper links:

```bash
python manage.py bootstrap_assessment_frameworks --schema demo --classify-existing --create-exam-links
```

Read-only readiness audit:

```bash
python manage.py audit_assessment_frameworks
python manage.py audit_assessment_frameworks --schema demo --fail-on-incomplete
```

## Rollout sequence

1. Apply migrations to shared and tenant schemas.
2. Run the bootstrap command with `--dry-run`.
3. Seed templates and classify records.
4. Configure schemes in the administrator UI.
5. Run the read-only audit.
6. Compare a sample of legacy and configurable results before publishing.
7. Keep legacy weights populated until the institution accepts the configured scheme.

## Rollback

Disable a scheme or clear nullable classification links. Existing scores and legacy weights continue to work. Do not reverse migrations after production data begins using assessment types or scheme links; use the additive disable-and-clear approach instead.
