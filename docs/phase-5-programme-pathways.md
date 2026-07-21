# Phase 5 — Subject combinations and programme pathways

Phase 5 adds an optional orchestration layer around the existing academic structure. It does not replace or rewrite programmes, levels, courses, class groups, streams, students, course offerings or enrollments.

## Source-of-truth guarantees

The following existing records remain authoritative:

- `academics.Program`;
- `academics.Level`;
- `academics.Course`;
- `academics.ClassGroup` and `academics.Stream`;
- `students.StudentProfile`;
- `academics.CourseOffering`;
- `academics.Enrollment`.

Phase 5 stores only pathway configuration and references to those records.

## New configuration

- `ProgrammePathway` — an existing programme scoped optionally by campus and education stage.
- `ProgrammePathwayLevel` — ordered existing levels, including one entry and one exit point.
- `SubjectCombination` — a named course combination within a pathway, optionally limited to one level.
- `SubjectCombinationCourse` — existing courses classified as core, elective or optional.
- `ClassGroupPathwayAssignment` — an optional standing or term-specific assignment for an existing class group.

A learner's active pathway is resolved from the learner's current stream and class group. No learner foreign key or historical record is changed.

## Resolution order

For a class group and term:

1. active, structurally valid assignments only;
2. exact academic-term assignment before a standing assignment;
3. higher pathway priority;
4. default flag;
5. stable primary-key tie-breaker.

When an assignment does not specify a combination, the highest-priority valid combination matching the class-group level is selected. If nothing valid matches, current academic operations continue unchanged.

## Rollout

Preview bootstrap changes:

```bash
python manage.py bootstrap_programme_pathways --dry-run
```

Create pathways and default combinations from existing programme/course links:

```bash
python manage.py bootstrap_programme_pathways
```

Bootstrap does **not** assign class groups, create offerings or enroll students.

Run the read-only audit:

```bash
python manage.py audit_programme_pathways
```

After configuration is complete, use the strict audit:

```bash
python manage.py audit_programme_pathways --fail-on-incomplete
```

## Offering planner

The administrator offering planner previews all courses in the resolved combination for a selected class group and term. It marks existing offerings as preserved and missing offerings separately.

Only an explicit **Create Missing Offerings** submission writes records. The operation:

- creates only missing `CourseOffering` rows;
- never edits or deletes existing offerings;
- never assigns teachers automatically;
- never creates or changes enrollments.

## Rollback

Application rollback is safe because existing academic records remain unchanged. If Phase 5 configuration is unused, reverting the application restores the previous behavior immediately. The additive tables can remain dormant or be removed through a controlled migration rollback after verifying that no institution depends on them.
