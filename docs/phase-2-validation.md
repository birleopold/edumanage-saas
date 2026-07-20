# Phase 2 validation checklist

Phase 2 is released only when the clean pull-request head passes all repository quality gates:

- migration drift detection;
- Django system and production deployment checks;
- template route verification;
- the complete Django test suite, including Phase 2 compatibility tests;
- Python dependency auditing;
- PostgreSQL shared-schema migration;
- PostgreSQL tenant-isolation proof.

The release must also confirm that no temporary payload or workflow files remain and that existing `AssessmentScore` and `ExamScore` records are not rewritten.
