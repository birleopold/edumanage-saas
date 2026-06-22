# Quizzes Portal

This feature exposes the existing quizzes app in the custom tenant portals.

## Mounted routes

Admin analytics:

- `/admin/quizzes/`

Teacher quiz builder:

- `/teacher/quizzes/`
- `/teacher/quizzes/create/`
- `/teacher/quizzes/<id>/`
- `/teacher/quizzes/<id>/edit/`
- `/teacher/quizzes/<id>/publish-toggle/`
- `/teacher/quizzes/<id>/questions/add/`
- `/teacher/quizzes/questions/<id>/choices/add/`
- `/teacher/quizzes/attempts/<id>/`
- `/teacher/quizzes/answers/<id>/grade/`

Student quiz taking:

- `/student/quizzes/`
- `/student/quizzes/<id>/take/`
- `/student/quizzes/attempts/<id>/result/`

## Teacher capabilities

Teachers can:

- create and edit quizzes for their own course offerings,
- set availability windows,
- assign students directly,
- assign all active learners in a class group,
- add questions,
- add answer choices,
- publish and unpublish quizzes,
- view attempts,
- manually grade answers that need review.

## Student capabilities

Students can:

- see available quizzes based on enrollment or direct assignment,
- start or continue an in-progress attempt,
- submit answers,
- view score and feedback after submission.

## Admin capabilities

Admins can view quiz performance summaries by:

- quiz,
- course,
- class group.

## Notes

The implementation uses the existing models: `Quiz`, `QuizQuestion`, `QuizQuestionChoice`, `QuizAttempt`, and `QuizAnswer`. Multiple-choice and true/false answers are auto-graded through the existing model methods. Short answer and essay responses can be reviewed manually from the teacher attempt detail page.

## Suggested verification

Run Django checks and smoke-test:

- teacher creates a quiz,
- teacher adds questions and choices,
- teacher publishes quiz,
- student sees and submits quiz,
- auto-graded answers update the attempt score,
- teacher manually grades a text answer,
- admin opens quiz analytics.
