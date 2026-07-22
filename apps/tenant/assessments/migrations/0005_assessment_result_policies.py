import django.db.models.deletion
from django.db import migrations, models


def bootstrap_assessment_policies(apps, schema_editor):
    Assessment = apps.get_model("assessments", "Assessment")
    AssessmentPolicy = apps.get_model("assessments", "AssessmentPolicy")
    AssessmentScore = apps.get_model("assessments", "AssessmentScore")
    AssessmentScorePolicy = apps.get_model(
        "assessments",
        "AssessmentScorePolicy",
    )

    assessment_rows = []
    existing_assessment_ids = set(
        AssessmentPolicy.objects.values_list("assessment_id", flat=True)
    )
    for assessment in Assessment.objects.select_related(
        "assessment_type",
        "offering",
    ).iterator():
        if assessment.pk in existing_assessment_ids:
            continue
        grading_mode = "NUMERIC"
        if (
            assessment.assessment_type_id
            and assessment.assessment_type.kind == "COMPETENCY"
        ):
            grading_mode = "COMPETENCY"
        assessment_rows.append(
            AssessmentPolicy(
                assessment_id=assessment.pk,
                grading_mode=grading_mode,
                responsible_teacher_id=assessment.offering.teacher_id,
            )
        )
    AssessmentPolicy.objects.bulk_create(assessment_rows, batch_size=500)

    existing_score_ids = set(
        AssessmentScorePolicy.objects.values_list("score_record_id", flat=True)
    )
    score_rows = [
        AssessmentScorePolicy(score_record_id=score.pk)
        for score in AssessmentScore.objects.only("pk").iterator()
        if score.pk not in existing_score_ids
    ]
    AssessmentScorePolicy.objects.bulk_create(score_rows, batch_size=1000)


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0004_grading_profiles_report_rules"),
        ("teachers", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssessmentPolicy",
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
                    "grading_mode",
                    models.CharField(
                        choices=[
                            ("NUMERIC", "Numeric marks and grades"),
                            ("COMPETENCY", "Competency or developmental assessment"),
                            ("MIXED", "Mixed numeric and competency assessment"),
                        ],
                        default="NUMERIC",
                        max_length=16,
                    ),
                ),
                (
                    "absence_policy",
                    models.CharField(
                        choices=[
                            ("MISSING", "Leave the result missing"),
                            ("ZERO", "Treat an unexplained absence as zero"),
                            ("EXCUSED", "Exclude an excused absence"),
                            ("DEFERRED", "Defer the result until a later assessment"),
                            ("MAKEUP_REQUIRED", "Require a makeup assessment"),
                        ],
                        default="MISSING",
                        max_length=24,
                    ),
                ),
                (
                    "show_on_report",
                    models.BooleanField(
                        default=True,
                        help_text="Include this assessment in report-card and transcript calculations when it is published.",
                    ),
                ),
                ("allow_makeup", models.BooleanField(default=False)),
                (
                    "competency_framework_key",
                    models.CharField(blank=True, max_length=96),
                ),
                ("deferred_until", models.DateField(blank=True, null=True)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "assessment",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="policy",
                        to="assessments.assessment",
                    ),
                ),
                (
                    "makeup_for",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="makeup_policy_records",
                        to="assessments.assessment",
                    ),
                ),
                (
                    "responsible_teacher",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="assessment_policies_responsible",
                        to="teachers.teacherprofile",
                    ),
                ),
            ],
            options={"ordering": ("assessment__offering", "assessment__name")},
        ),
        migrations.CreateModel(
            name="AssessmentScorePolicy",
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
                    "attendance_status",
                    models.CharField(
                        choices=[
                            ("PRESENT", "Present"),
                            ("ABSENT", "Absent"),
                            ("EXCUSED", "Excused absence"),
                            ("DEFERRED", "Deferred"),
                            ("MAKEUP_PENDING", "Makeup assessment pending"),
                        ],
                        default="PRESENT",
                        max_length=20,
                    ),
                ),
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
                ("deferred_until", models.DateField(blank=True, null=True)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "makeup_completed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="completed_makeup_for",
                        to="assessments.assessmentscore",
                    ),
                ),
                (
                    "score_record",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="policy",
                        to="assessments.assessmentscore",
                    ),
                ),
            ],
            options={
                "ordering": (
                    "score_record__student__last_name",
                    "score_record__student__first_name",
                )
            },
        ),
        migrations.RunPython(
            bootstrap_assessment_policies,
            migrations.RunPython.noop,
        ),
    ]
