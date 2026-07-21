from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0003_gradingscale_stream_graderange"),
        ("assessments", "0003_configurable_assessment_framework"),
        ("education_frameworks", "0001_initial"),
        ("orgsettings", "0006_merge_20260624_1447"),
    ]

    operations = [
        migrations.CreateModel(
            name="GradingProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=48, unique=True)),
                ("name", models.CharField(max_length=128)),
                ("description", models.TextField(blank=True)),
                (
                    "overall_aggregation",
                    models.CharField(
                        choices=[
                            ("MEAN", "Mean of completed course results"),
                            ("CREDIT_WEIGHTED", "Credit-weighted mean"),
                        ],
                        default="MEAN",
                        max_length=24,
                    ),
                ),
                (
                    "incomplete_result_policy",
                    models.CharField(
                        choices=[
                            ("EXCLUDE", "Exclude incomplete courses from the overall result"),
                            ("ZERO", "Treat incomplete courses as zero"),
                            ("INCOMPLETE", "Keep the report incomplete until every course is complete"),
                        ],
                        default="EXCLUDE",
                        max_length=16,
                    ),
                ),
                (
                    "pass_percentage",
                    models.DecimalField(
                        decimal_places=2,
                        default=50,
                        max_digits=5,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0")),
                            django.core.validators.MaxValueValidator(Decimal("100")),
                        ],
                    ),
                ),
                (
                    "promotion_percentage",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=5,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0")),
                            django.core.validators.MaxValueValidator(Decimal("100")),
                        ],
                    ),
                ),
                ("minimum_passed_courses", models.PositiveSmallIntegerField(blank=True, null=True)),
                (
                    "decimal_places",
                    models.PositiveSmallIntegerField(
                        default=2,
                        validators=[django.core.validators.MaxValueValidator(4)],
                    ),
                ),
                ("priority", models.IntegerField(default=0)),
                ("is_default", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "academic_term",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="grading_profiles",
                        to="academics.academicterm",
                    ),
                ),
                (
                    "campus",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="grading_profiles",
                        to="orgsettings.campus",
                    ),
                ),
                (
                    "grading_scale",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="grading_profiles",
                        to="academics.gradingscale",
                    ),
                ),
                (
                    "level",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="grading_profiles",
                        to="academics.level",
                    ),
                ),
                (
                    "program",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="grading_profiles",
                        to="academics.program",
                    ),
                ),
                (
                    "stage",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="grading_profiles",
                        to="education_frameworks.educationstage",
                    ),
                ),
            ],
            options={"ordering": ("-priority", "-is_default", "name")},
        ),
        migrations.CreateModel(
            name="ReportRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("report_title", models.CharField(blank=True, max_length=128)),
                ("result_label", models.CharField(default="Result", max_length=48)),
                ("promotion_label", models.CharField(default="Progression", max_length=48)),
                ("show_percentage", models.BooleanField(default=True)),
                ("show_grade", models.BooleanField(default=True)),
                ("show_remark", models.BooleanField(default=True)),
                ("show_published_scores", models.BooleanField(default=True)),
                ("show_assessment_details", models.BooleanField(default=True)),
                ("show_component_breakdown", models.BooleanField(default=True)),
                ("show_promotion_status", models.BooleanField(default=False)),
                ("show_teacher_comments", models.BooleanField(default=True)),
                ("show_head_comments", models.BooleanField(default=True)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "grading_profile",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="report_rule",
                        to="assessments.gradingprofile",
                    ),
                ),
            ],
        ),
    ]
