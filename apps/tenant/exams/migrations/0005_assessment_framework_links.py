import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0003_configurable_assessment_framework"),
        ("exams", "0004_rename_exams_anticheat_idx_exams_exama_attempt_42b1d7_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="exampaper",
            name="assessment_type",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="exam_papers",
                to="assessments.assessmenttype",
            ),
        ),
        migrations.AddField(
            model_name="exampaper",
            name="weighting_component",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="exam_papers",
                to="assessments.assessmentweightingcomponent",
            ),
        ),
        migrations.AddField(
            model_name="exampaper",
            name="linked_assessment",
            field=models.OneToOneField(
                blank=True,
                help_text="Optional compatibility link; existing exam scores remain in the exams module.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="exam_paper",
                to="assessments.assessment",
            ),
        ),
    ]
