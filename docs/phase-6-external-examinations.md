# Phase 6 — Candidate and external examination management

Phase 6 adds an external-examination orchestration layer around EduManage's existing internal examination system.

## Source-of-truth guarantees

The following records remain authoritative and are not copied, replaced or rewritten:

- `exams.Exam`, `ExamPaper`, `ExamSchedule` and `SeatAllocation`;
- `exams.OnlineExamAttempt` and related online-exam records;
- `exams.ExamScore` and `ExamAnalytics`;
- `students.StudentProfile`;
- academic course offerings and enrollments;
- existing student, parent and administrator exam/report routes.

External boards, sessions, candidate registrations and official external results are additive. An external subject may optionally link to an existing internal paper, and an external result may optionally link to an existing `ExamScore`, but those links never update the internal mark.

## Configuration workflow

1. Add an external examination board.
2. Add one or more examination centres.
3. Add an external examination session and configure its scope.
4. Add external subjects using existing `academics.Course` records.
5. Open candidate registration.
6. Preview and register eligible learners.
7. Add compulsory subjects in bulk and optional subjects deliberately per candidate.
8. Export candidate data for board submission.
9. Dry-run the result CSV, correct validation errors and then commit the import.

Administrator page:

```text
/admin/exams/external/
```

## Candidate registration safety

Eligibility is derived from existing active learner records and the learner's current campus, stream, class group, level and programme. Candidate registration:

- does not change the learner profile;
- does not change stream or class placement;
- does not create or modify course enrollments;
- does not create internal exam scores;
- is idempotent for each session and learner;
- generates candidate numbers under a database lock.

The command is dry-run by default:

```bash
python manage.py bootstrap_external_exam_candidates --session UACE-2029
```

Apply candidate registration explicitly:

```bash
python manage.py bootstrap_external_exam_candidates \
    --session UACE-2029 \
    --apply
```

Include missing compulsory subject registrations:

```bash
python manage.py bootstrap_external_exam_candidates \
    --session UACE-2029 \
    --include-compulsory-subjects \
    --apply
```

For one tenant:

```bash
python manage.py bootstrap_external_exam_candidates \
    --schema demo \
    --session UACE-2029
```

## Result CSV

Required columns:

```text
candidate_number,subject_code
```

Optional columns:

```text
score,percentage,grade,result_status,source_reference
```

Valid result statuses are:

```text
PENDING,PASS,FAIL,ABSENT,WITHHELD,EXEMPT
```

The web form defaults to dry-run. A committed file with any validation error is rejected as a whole, preventing partial official-result imports.

## Readiness audit

Read-only audit:

```bash
python manage.py audit_external_exams
```

Strict deployment or rollout gate:

```bash
python manage.py audit_external_exams --fail-on-incomplete
```

One tenant:

```bash
python manage.py audit_external_exams \
    --schema demo \
    --fail-on-incomplete
```

## Rollback

Application rollback is safe because internal exams, scores, enrollments and learners are unchanged. Reverting the application restores the previous internal-exam experience. Phase 6 tables can remain unused until a controlled maintenance window is available for migration rollback.
