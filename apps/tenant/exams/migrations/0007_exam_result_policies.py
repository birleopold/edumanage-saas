import django.db.models.deletion
from django.db import migrations, models


def bootstrap_exam_policies(apps, schema_editor):
    ExamPaper = apps.get_model("exams", "ExamPaper")
    ExamPaperPolicy = apps.get_model("exams", "ExamPaperPolicy")
    ExamScore = apps.get_model("exams", "ExamScore")
    ExamScorePolicy = apps.get_model("exams", "ExamScorePolicy")

    existing_paper_ids = set(
        ExamPaperPolicy.objects.values_list("paper_id", flat=True)
    )
    paper_rows = []
    for paper in ExamPaper.objects.select_related(
        "assessment_type",
        "offering",
    ).iterator():
        if paper.pk in existing_paper_ids:
            continue
        grading_mode = "NUMERIC"
        if paper.assessment_type_id and paper.assessment_type.kind == "COMPETENCY":
            grading_mode = "COMPETENCY"
        paper_rows.append(
            ExamPaperPolicy(
                paper_id=paper.pk,
                grading_mode=grading_mode,
                show_on_report=paper.report_cards_enabled,
                responsible_teacher_id=paper.offering.teacher_id,
            )
        )
    ExamPaperPolicy.objects.bulk_create(paper_rows, batch_size=500)

    existing_score_ids = set(
        ExamScorePolicy.objects.values_list("score_record_id", flat=True)
    )
    score_rows = [
        ExamScorePolicy(score_record_id=score.pk)
        for score in ExamScore.objects.only("pk").iterator()
        if score.pk not in existing_score_ids
    ]
    ExamScorePolicy.objects.bulk_create(score_rows, batch_size=1000)


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0005_assessment_result_policies"),
        ("exams", "0006_external_exam_candidates"),
        ("teachers", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExamPaperPolicy",
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
                            ("DEFERRED", "Defer the result until a later paper"),
                            ("MAKEUP_REQUIRED", "Require a makeup paper"),
                        ],
                        default="MISSING",
                        max_length=24,
                    ),
                ),
                (
                    "show_on_report",
                    models.BooleanField(
                        default=True,
                        help_text="Include this published paper in report-card and transcript calculations.",
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
                    "makeup_for",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="makeup_policy_records",
                        to="exams.exampaper",
                    ),
                ),
                (
                    "paper",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="policy",
                        to="exams.exampaper",
                    ),
                ),
                (
                    "responsible_teacher",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="exam_paper_policies_responsible",
                        to="teachers.teacherprofile",
                    ),
                ),
            ],
            options={
                "ordering": (
                    "paper__exam",
                    "paper__offering__course__name",
                )
            },
        ),
        migrations.CreateModel(
            name="ExamScorePolicy",
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
                            ("MAKEUP_PENDING", "Makeup paper pending"),
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
                        to="exams.examscore",
                    ),
                ),
                (
                    "score_record",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="policy",
                        to="exams.examscore",
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
            bootstrap_exam_policies,
            migrations.RunPython.noop,
        ),
    ]
