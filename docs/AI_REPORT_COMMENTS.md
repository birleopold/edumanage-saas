# AI-Assisted Report Comments

EduManage provides deterministic report-card comment suggestions in the assessment grading workflow.

## Where It Appears

- Teacher grading page: `/teacher/assessments/<assessment_id>/grade/`
- Admin assessment scores page: `/admin/assessments/<assessment_id>/scores/`
- Teacher JSON endpoint: `/teacher/assessments/<assessment_id>/comment-suggestions/`

Teachers can review the suggested comment and use the `Use comment` action to place it into the dedicated report-comment field. The score row keeps both the teacher's short note and the longer report-card comment.

## Signals Used

The suggestion engine considers:

- Current assessment percentage and performance band
- Improvement trend against the previous assessment in the same course offering
- Term attendance percentage
- Conduct/discipline incident count
- Course name and student first name

## Persistence

The teacher JSON endpoint also refreshes the existing analytics `ReportCardCommentSuggestion` record for the student and term. This keeps the analytics progress pages aligned with the latest assessment comments without adding a new database table.

Accepted comments are stored on `AssessmentScore.report_comment`. When a suggestion is accepted, `AssessmentScore.report_comment_ai_assisted` is set so report cards can show the comment was AI-assisted.

## Current Scope

This feature does not call an external AI provider. It uses rule-based generation so it works offline, is fast, and is safe for schools without AI API credentials. A future provider-backed version can replace or augment the suggestion service behind the same view/API surfaces.
