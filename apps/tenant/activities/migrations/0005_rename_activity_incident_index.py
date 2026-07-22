from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("activities", "0004_activity_incidents_certificates"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="activityincident",
            old_name="activities__student_d6f0ad_idx",
            new_name="activities__student_3eb7ec_idx",
        ),
    ]
