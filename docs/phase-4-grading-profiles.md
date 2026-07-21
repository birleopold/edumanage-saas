# Phase 4 — Level-specific grading profiles and report rules

Phase 4 adds an additive configuration layer around the existing grading and report-card system.

## Source-of-truth guarantees

The following records remain authoritative and are not copied or rewritten:

- `academics.GradingScale` and `academics.GradeRange`;
- `assessments.AssessmentScore`;
- `exams.ExamScore`;
- existing assessment, examination, student, parent and report-card routes.

A `GradingProfile` only selects an existing grading scale for a matching campus, education stage, level, programme and academic term. `ReportRule` controls report-card presentation and progression status.

## Resolution order

Only active, structurally valid profiles participate. Matching is deterministic:

1. highest priority;
2. most exact scope fields;
3. default flag;
4. profile primary key.

When no profile matches, EduManage keeps the existing A–F grading bands and current mean-based report-card calculation.

## Rollout

Preview the default-profile bootstrap:

```bash
python manage.py bootstrap_grading_profiles --dry-run
```

Create a default profile from each tenant's existing active default grading scale:

```bash
python manage.py bootstrap_grading_profiles
```

Run the read-only audit:

```bash
python manage.py audit_grading_profiles --fail-on-incomplete
```

Administrators can then add narrower profiles from **Assessments → Grading Profiles**.

## Report behavior

Profiles may configure:

- existing grading scale;
- pass percentage;
- mean or credit-weighted overall aggregation;
- incomplete-course handling;
- optional promotion percentage and minimum passed-course count;
- decimal precision.

Report rules may show or hide percentage, grade, remark, score counts, assessment detail, weighting-component breakdown and promotion status.

## Rollback

Application rollback is safe because existing marks and grading scales are unchanged. Reverting the application restores the previous report-card behavior. The additive Phase 4 tables can remain unused until the migration is rolled back during a controlled maintenance window.
