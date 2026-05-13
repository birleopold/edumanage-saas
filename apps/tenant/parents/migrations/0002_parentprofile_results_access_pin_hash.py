from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parents", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="parentprofile",
            name="results_access_pin_hash",
            field=models.CharField(
                blank=True,
                max_length=128,
                help_text="Hashed PIN (4–6 digits). When set, parent must enter PIN to view children's published assessment results.",
            ),
        ),
    ]
