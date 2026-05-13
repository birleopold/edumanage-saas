from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0004_studentprofile_stream"),
    ]

    operations = [
        migrations.AddField(
            model_name="studentprofile",
            name="district",
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="subcounty",
            field=models.CharField(blank=True, max_length=128, verbose_name="Sub-county"),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="parish",
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="nin",
            field=models.CharField(
                blank=True,
                help_text="National Identification Number (optional).",
                max_length=32,
                verbose_name="NIN",
            ),
        ),
        migrations.AddField(
            model_name="studentprofile",
            name="learner_id",
            field=models.CharField(
                blank=True,
                help_text="Government / EMIS learner identifier when applicable.",
                max_length=64,
                verbose_name="Learner ID",
            ),
        ),
    ]
