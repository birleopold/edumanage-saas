import django.db.models.deletion
from django.db import migrations, models


def migrate_stage_configuration(apps, schema_editor):
    CampusEducationStage = apps.get_model(
        "education_frameworks",
        "CampusEducationStage",
    )
    GradingScale = apps.get_model("academics", "GradingScale")

    valid_scale_ids = set(GradingScale.objects.values_list("pk", flat=True))
    rows = CampusEducationStage.objects.select_related(
        "stage",
        "framework_stage",
    )
    for row in rows.iterator():
        update_fields = []
        if (
            row.legacy_grading_scale_id
            and row.legacy_grading_scale_id in valid_scale_ids
        ):
            row.grading_scale_id = row.legacy_grading_scale_id
            update_fields.append("grading_scale")

        if row.framework_stage_id:
            row.candidate_class = bool(row.framework_stage.candidate_class)
            update_fields.append("candidate_class")

        stage_code = row.stage.code
        if stage_code == "ECD":
            row.default_assessment_mode = "COMPETENCY"
            row.report_mode = "COMPETENCY"
            row.supports_promotion_decisions = False
            update_fields.extend(
                [
                    "default_assessment_mode",
                    "report_mode",
                    "supports_promotion_decisions",
                ]
            )
        elif stage_code in {"TERTIARY", "UNIVERSITY"}:
            row.report_mode = "TRANSCRIPT"
            update_fields.append("report_mode")

        if update_fields:
            row.save(update_fields=list(dict.fromkeys(update_fields)))


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0003_gradingscale_stream_graderange"),
        ("education_frameworks", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="campuseducationstage",
            old_name="grading_scale_id",
            new_name="legacy_grading_scale_id",
        ),
        migrations.AddField(
            model_name="campuseducationstage",
            name="grading_scale",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="education_stage_configurations",
                to="academics.gradingscale",
            ),
        ),
        migrations.AddField(
            model_name="campuseducationstage",
            name="default_assessment_mode",
            field=models.CharField(
                choices=[
                    ("NUMERIC", "Numeric marks and grades"),
                    ("COMPETENCY", "Competency or developmental assessment"),
                    ("MIXED", "Mixed numeric and competency assessment"),
                ],
                default="NUMERIC",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="campuseducationstage",
            name="report_mode",
            field=models.CharField(
                choices=[
                    ("STANDARD", "Standard report card"),
                    ("COMPETENCY", "Competency or developmental report"),
                    ("TRANSCRIPT", "Transcript-oriented report"),
                    ("CUSTOM", "Custom report layout"),
                ],
                default="STANDARD",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="campuseducationstage",
            name="candidate_class",
            field=models.BooleanField(
                default=False,
                help_text="Mark this campus stage as containing external-examination candidate classes.",
            ),
        ),
        migrations.AddField(
            model_name="campuseducationstage",
            name="supports_promotion_decisions",
            field=models.BooleanField(
                default=True,
                help_text="Allow result policies to produce progression or promotion decisions for this stage.",
            ),
        ),
        migrations.RunPython(
            migrate_stage_configuration,
            migrations.RunPython.noop,
        ),
    ]
