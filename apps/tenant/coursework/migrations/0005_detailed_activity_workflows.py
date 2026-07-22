import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


DETAILED_KIND_MAP = {
    "RESOURCE": "RESOURCE",
    "ASSIGNMENT": "ASSIGNMENT",
    "PROJECT": "PROJECT",
    "PRACTICAL": "PRACTICAL",
    "DISCUSSION": "DISCUSSION",
    "LIVE_CLASS": "LIVE_CLASS",
    "VIDEO": "VIDEO",
    "QUIZ": "QUIZ",
    "OTHER": "OTHER",
}


def infer_legacy_detail(activity):
    title = str(activity.title_snapshot or "").lower()
    if "weekend" in title:
        return "WEEKEND_ASSIGNMENT"
    if "classwork" in title or "class work" in title:
        return "CLASSWORK"
    if "essay" in title:
        return "ESSAY"
    if "lab report" in title or "laboratory report" in title:
        return "LAB_REPORT"
    if "fieldwork" in title or "field work" in title:
        return "FIELDWORK"
    if "group assignment" in title or "group work" in title:
        return "GROUP_ASSIGNMENT"
    if "reading exercise" in title or "reading task" in title:
        return "READING_EXERCISE"
    if "research" in title:
        return "RESEARCH_WORK"
    if "activity of integration" in title or title.strip() == "aoi":
        return "ACTIVITY_OF_INTEGRATION"
    return DETAILED_KIND_MAP.get(activity.kind, "OTHER")


def bootstrap_workflows(apps, schema_editor):
    LearningActivity = apps.get_model("coursework", "LearningActivity")
    LearningActivityProfile = apps.get_model(
        "coursework",
        "LearningActivityProfile",
    )
    AssignmentSubmission = apps.get_model("coursework", "AssignmentSubmission")
    SubmissionWorkflow = apps.get_model("coursework", "SubmissionWorkflow")

    existing_activity_ids = set(
        LearningActivityProfile.objects.values_list("activity_id", flat=True)
    )
    activity_rows = []
    for activity in LearningActivity.objects.iterator():
        if activity.pk in existing_activity_ids:
            continue
        detailed_kind = infer_legacy_detail(activity)
        activity_rows.append(
            LearningActivityProfile(
                activity_id=activity.pk,
                detailed_kind=detailed_kind,
                group_work=detailed_kind == "GROUP_ASSIGNMENT",
                maximum_attempts=1,
            )
        )
    LearningActivityProfile.objects.bulk_create(activity_rows, batch_size=500)

    existing_submission_ids = set(
        SubmissionWorkflow.objects.values_list("submission_id", flat=True)
    )
    workflow_rows = []
    for submission in AssignmentSubmission.objects.select_related("assignment").iterator():
        if submission.pk in existing_submission_ids:
            continue
        status = "DRAFT"
        is_late = False
        first_submitted_at = submission.submitted_at
        if submission.marked_at:
            status = "MARKED"
        elif submission.submitted_at:
            due_at = submission.assignment.due_date
            is_late = bool(due_at and submission.submitted_at > due_at)
            status = "LATE" if is_late else "SUBMITTED"
        workflow_rows.append(
            SubmissionWorkflow(
                submission_id=submission.pk,
                status=status,
                is_late=is_late,
                first_submitted_at=first_submitted_at,
                attempt_count=1,
            )
        )
    SubmissionWorkflow.objects.bulk_create(workflow_rows, batch_size=1000)


class Migration(migrations.Migration):
    dependencies = [
        ("coursework", "0004_unified_learning_activities"),
        ("students", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LearningActivityProfile",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "detailed_kind",
                    models.CharField(
                        choices=[
                            ("RESOURCE", "Learning resource"),
                            ("ASSIGNMENT", "Individual assignment"),
                            ("PROJECT", "Project"),
                            ("PRACTICAL", "Practical activity"),
                            ("DISCUSSION", "Discussion or debate"),
                            ("LIVE_CLASS", "Live class"),
                            ("VIDEO", "Video lesson"),
                            ("QUIZ", "Quiz or short task"),
                            ("CLASSWORK", "Classwork"),
                            ("WEEKEND_ASSIGNMENT", "Weekend assignment"),
                            ("ESSAY", "Essay"),
                            ("LAB_REPORT", "Laboratory report"),
                            ("FIELDWORK", "Fieldwork"),
                            ("GROUP_ASSIGNMENT", "Group assignment"),
                            ("READING_EXERCISE", "Reading exercise"),
                            ("RESEARCH_WORK", "Research work"),
                            ("ACTIVITY_OF_INTEGRATION", "Activity of Integration"),
                            ("OTHER", "Other learning activity"),
                        ],
                        default="OTHER",
                        max_length=32,
                    ),
                ),
                ("group_work", models.BooleanField(default=False)),
                ("resubmission_allowed", models.BooleanField(default=False)),
                ("maximum_attempts", models.PositiveSmallIntegerField(default=1)),
                ("late_grace_minutes", models.PositiveIntegerField(default=0)),
                ("competency_tracking", models.BooleanField(default=False)),
                (
                    "competency_framework_key",
                    models.CharField(blank=True, max_length=96),
                ),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "activity",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workflow_profile",
                        to="coursework.learningactivity",
                    ),
                ),
            ],
            options={
                "ordering": (
                    "activity__position",
                    "activity__title_snapshot",
                )
            },
        ),
        migrations.CreateModel(
            name="AssignmentGroup",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=128)),
                ("capacity", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "activity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignment_groups",
                        to="coursework.learningactivity",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="coursework_groups_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("activity__title_snapshot", "name")},
        ),
        migrations.CreateModel(
            name="SubmissionWorkflow",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DRAFT", "Draft"),
                            ("SUBMITTED", "Submitted"),
                            ("LATE", "Submitted late"),
                            ("EXCUSED_LATE", "Late submission excused"),
                            ("RETURNED", "Returned to learner"),
                            ("RESUBMISSION_REQUIRED", "Resubmission required"),
                            ("RESUBMITTED", "Resubmitted"),
                            ("MARKED", "Marked"),
                        ],
                        default="DRAFT",
                        max_length=24,
                    ),
                ),
                ("is_late", models.BooleanField(default=False)),
                ("late_excused", models.BooleanField(default=False)),
                ("late_reason", models.TextField(blank=True)),
                ("attempt_count", models.PositiveSmallIntegerField(default=1)),
                ("first_submitted_at", models.DateTimeField(blank=True, null=True)),
                ("returned_at", models.DateTimeField(blank=True, null=True)),
                ("resubmitted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "competency_rating",
                    models.CharField(
                        choices=[
                            ("ACHIEVED", "Achieved"),
                            ("DEVELOPING", "Developing"),
                            ("NEEDS_SUPPORT", "Needs support"),
                            ("NOT_ASSESSED", "Not assessed"),
                        ],
                        default="NOT_ASSESSED",
                        max_length=24,
                    ),
                ),
                ("competency_evidence", models.TextField(blank=True)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "submission",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workflow",
                        to="coursework.assignmentsubmission",
                    ),
                ),
            ],
            options={"ordering": ("-updated_at",)},
        ),
        migrations.CreateModel(
            name="AssignmentGroupMember",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("MEMBER", "Member"),
                            ("LEADER", "Group leader"),
                            ("SECRETARY", "Secretary"),
                            ("PRESENTER", "Presenter"),
                            ("OTHER", "Other"),
                        ],
                        default="MEMBER",
                        max_length=16,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("joined_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="coursework.assignmentgroup",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="coursework_group_memberships",
                        to="students.studentprofile",
                    ),
                ),
            ],
            options={
                "ordering": (
                    "group",
                    "student__last_name",
                    "student__first_name",
                )
            },
        ),
        migrations.CreateModel(
            name="GroupSubmission",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("text_answer", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DRAFT", "Draft"),
                            ("SUBMITTED", "Submitted"),
                            ("LATE", "Submitted late"),
                            ("EXCUSED_LATE", "Late submission excused"),
                            ("RETURNED", "Returned to learner"),
                            ("RESUBMISSION_REQUIRED", "Resubmission required"),
                            ("RESUBMITTED", "Resubmitted"),
                            ("MARKED", "Marked"),
                        ],
                        default="DRAFT",
                        max_length=24,
                    ),
                ),
                ("attempt_count", models.PositiveSmallIntegerField(default=1)),
                ("first_submitted_at", models.DateTimeField(blank=True, null=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("is_late", models.BooleanField(default=False)),
                ("late_excused", models.BooleanField(default=False)),
                ("late_reason", models.TextField(blank=True)),
                (
                    "score",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=8,
                        null=True,
                    ),
                ),
                ("feedback", models.TextField(blank=True)),
                (
                    "competency_rating",
                    models.CharField(
                        choices=[
                            ("ACHIEVED", "Achieved"),
                            ("DEVELOPING", "Developing"),
                            ("NEEDS_SUPPORT", "Needs support"),
                            ("NOT_ASSESSED", "Not assessed"),
                        ],
                        default="NOT_ASSESSED",
                        max_length=24,
                    ),
                ),
                ("competency_evidence", models.TextField(blank=True)),
                ("marked_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "activity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="group_submissions",
                        to="coursework.learningactivity",
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="submissions",
                        to="coursework.assignmentgroup",
                    ),
                ),
                (
                    "marked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="marked_group_submissions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "submitted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="coursework_group_submissions_made",
                        to="students.studentprofile",
                    ),
                ),
            ],
            options={"ordering": ("-updated_at",)},
        ),
        migrations.CreateModel(
            name="GroupSubmissionAttachment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "file",
                    models.FileField(
                        upload_to="coursework/group-submissions/%Y/%m/"
                    ),
                ),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "submission",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attachments",
                        to="coursework.groupsubmission",
                    ),
                ),
            ],
            options={"ordering": ("-uploaded_at",)},
        ),
        migrations.AddConstraint(
            model_name="assignmentgroup",
            constraint=models.UniqueConstraint(
                fields=("activity", "name"),
                name="uniq_coursework_activity_group",
            ),
        ),
        migrations.AddConstraint(
            model_name="assignmentgroupmember",
            constraint=models.UniqueConstraint(
                fields=("group", "student"),
                name="uniq_coursework_group_student",
            ),
        ),
        migrations.AddConstraint(
            model_name="groupsubmission",
            constraint=models.UniqueConstraint(
                fields=("activity", "group"),
                name="uniq_coursework_activity_group_submission",
            ),
        ),
        migrations.RunPython(bootstrap_workflows, migrations.RunPython.noop),
    ]
