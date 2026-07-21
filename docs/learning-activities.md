# Phase 3 unified learning activities

## Purpose

Phase 3 adds an orchestration layer around the existing coursework module. `LearningMaterial`, `Assignment`, `AssignmentSubmission`, `CourseworkComment`, `CourseworkProgress` and their attachment tables remain the operational source records. The new `LearningActivity` row adds a stable cross-source identity and configurable learning policy without introducing a second content, submission, marks or progress store.

## Activity coverage

Existing materials and assignments are classified into internationally neutral kinds:

- Learning resource
- Assignment
- Project
- Practical activity
- Discussion
- Live class
- Video lesson
- Quiz or short task
- Other learning activity

Optional JSON aliases can provide country or institution wording without changing the neutral kind. Activity policy supports sequencing, estimated duration, completion rules, submission rules and optional Phase 2 assessment-type or weighting-component links.

## Compatibility guarantees

- No existing coursework model, table, field or URL is removed or renamed.
- Existing administrator, teacher, student, parent and mobile coursework routes continue to read their current source tables.
- Existing attachment files remain attached to their current material, assignment or submission record.
- Existing submission text, scores, feedback, comments, timestamps and progress percentages are never copied into a competing table.
- The only metadata added to submission, comment and progress records is a nullable `activity_id` compatibility link.
- Existing material and assignment values remain authoritative. The activity `title_snapshot` is used for readiness and search and is safely refreshed when the source title changes.
- Administrator-edited activity policy is preserved during normal synchronization. Classification and default policies change only when `--refresh-classification` is explicitly requested.

## Deployment

After pulling the Phase 3 merge and applying tenant migrations, preview the rollout:

```bash
python manage.py bootstrap_learning_activities --dry-run
python manage.py audit_learning_activities
```

Create missing orchestration rows and nullable metadata links:

```bash
python manage.py bootstrap_learning_activities
python manage.py audit_learning_activities --fail-on-incomplete
```

For one tenant:

```bash
python manage.py bootstrap_learning_activities --schema demo --dry-run
python manage.py bootstrap_learning_activities --schema demo
python manage.py audit_learning_activities --schema demo --fail-on-incomplete
```

Use `--refresh-classification` only when administrators intentionally want generated activity kinds and default completion/submission policies recalculated from source wording.

## Administrator workflow

Open **Coursework → Unified Learning Activities**. The setup page shows missing source links, stale snapshots and unlinked submission/comment/progress metadata. **Synchronize safely** creates only missing orchestration and compatibility links. Each activity can then be configured with its kind, order, estimated duration, completion policy, submission policy and optional Phase 2 assessment links.

## Rollback

The feature can be rolled back operationally without touching coursework data:

1. Stop using the unified activity setup page and services.
2. Leave nullable `activity_id` links in place or clear them with a controlled script.
3. Keep existing material, assignment, submission, comment and progress routes active.
4. Reverse the Phase 3 migration only after confirming no later migration depends on `LearningActivity`.

Deleting a `LearningActivity` never deletes its source material or assignment through application workflows. Source deletion retains its existing behavior and removes the corresponding orchestration row through the database relationship.

## Validation gate

A Phase 3 release is ready only when migration drift, Django checks, production deploy checks, route verification, the complete Django test suite, dependency audit, PostgreSQL shared migration and PostgreSQL tenant-isolation proof all pass.
