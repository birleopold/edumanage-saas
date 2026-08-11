from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0005_subject_role_policies"),
        ("assessments", "0005_assessment_result_policies"),
    ]

    operations = [
        migrations.AddField(
            model_name="gradingprofile",
            name="course",
            field=models.ForeignKey(
                blank=True,
                help_text="Optional subject/course override. Leave blank for a general grading rule.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="grading_profiles",
                to="academics.course",
            ),
        ),
    ]
