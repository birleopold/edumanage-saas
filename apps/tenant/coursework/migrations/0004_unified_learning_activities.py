# Generated for Phase 3 unified learning activities.

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0003_configurable_assessment_framework"),
        ("coursework", "0003_rename_coursework_student_material_idx_coursework__student_40582d_idx_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="LearningActivity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("RESOURCE", "Learning resource"),
                            ("ASSIGNMENT", "Assignment"),
                            ("PROJECT", "Project"),
                            ("PRACTICAL", "Practical activity"),
                            ("DISCUSSION", "Discussion"),
                            ("LIVE_CLASS", "Live class"),
                            ("VIDEO", "Video lesson"),
                            ("QUIZ", "Quiz or short task"),
                            ("OTHER", "Other learning activity"),
                        ],
                        default="OTHER",
                        max_length=24,
                    ),
                ),
                ("title_snapshot", models.CharField(max_length=200)),
                ("position", models.PositiveIntegerField(default=0)),
                ("estimated_minutes", models.PositiveIntegerField(blank=True, null=True)),
                (
                    "completion_policy",
                    models.CharField(
                        choices=[
                            ("NONE", "No completion tracking"),
                            ("VIEW", "Complete after viewing"),
                            ("MANUAL", "Learner marks complete"),
                            ("SUBMISSION", "Complete after submission"),
                            ("SCORE", "Complete after marking"),
                        ],
                        default="MANUAL",
                        max_length=16,
                    ),
                ),
                (
                    "submission_policy",
                    models.CharField(
                        choices=[
                            ("NONE", "No submission"),
                            ("OPTIONAL", "Optional submission"),
                            ("REQUIRED", "Required submission"),
                        ],
                        default="NONE",
                        max_length=16,
                    ),
                ),
                ("local_aliases", models.JSONField(blank=True, default=dict)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "assessment_type",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="learning_activities",
                        to="assessments.assessmenttype",
                    ),
                ),
                (
                    "assignment",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="unified_activity",
                        to="coursework.assignment",
                    ),
                ),
                (
                    "material",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="unified_activity",
                        to="coursework.learningmaterial",
                    ),
                ),
                (
                    "weighting_component",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="learning_activities",
                        to="assessments.assessmentweightingcomponent",
                    ),
                ),
            ],
            options={
                "ordering": ("position", "-created_at"),
                "indexes": [
                    models.Index(fields=["kind", "is_active"], name="coursework__kind_76ac4a_idx"),
                    models.Index(fields=["position", "created_at"], name="coursework__positio_147252_idx"),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=(
                            models.Q(("assignment__isnull", True), ("material__isnull", False))
                            | models.Q(("assignment__isnull", False), ("material__isnull", True))
                        ),
                        name="coursework_activity_exactly_one_source",
                    )
                ],
            },
        ),
        migrations.AddField(
            model_name="assignmentsubmission",
            name="activity",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="submissions",
                to="coursework.learningactivity",
            ),
        ),
        migrations.AddField(
            model_name="courseworkcomment",
            name="activity",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="comments",
                to="coursework.learningactivity",
            ),
        ),
        migrations.AddField(
            model_name="courseworkprogress",
            name="activity",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="progress_records",
                to="coursework.learningactivity",
            ),
        ),
        migrations.AddIndex(
            model_name="courseworkprogress",
            index=models.Index(fields=["student", "activity"], name="coursework__student_db914e_idx"),
        ),
    ]
