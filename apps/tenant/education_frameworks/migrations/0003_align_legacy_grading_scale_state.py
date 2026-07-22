from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("education_frameworks", "0002_stage_policy_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="campuseducationstage",
            name="legacy_grading_scale_id",
            field=models.PositiveBigIntegerField(
                blank=True,
                editable=False,
                help_text=(
                    "Legacy compatibility identifier retained during the Phase 1 migration."
                ),
                null=True,
            ),
        ),
    ]
