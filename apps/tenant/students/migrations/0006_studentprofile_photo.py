from django.db import migrations, models

import apps.tenant.students.models


class Migration(migrations.Migration):
    dependencies = [
        ("students", "0005_studentprofile_demographics"),
    ]

    operations = [
        migrations.AddField(
            model_name="studentprofile",
            name="photo",
            field=models.ImageField(
                blank=True,
                help_text="Portrait used on student ID cards and official school documents.",
                upload_to=apps.tenant.students.models.student_photo_upload_to,
            ),
        ),
    ]
