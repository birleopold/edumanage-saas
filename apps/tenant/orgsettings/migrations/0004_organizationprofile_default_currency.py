from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orgsettings", "0003_campus_student_numbering"),
    ]

    operations = [
        migrations.AddField(
            model_name="organizationprofile",
            name="default_currency",
            field=models.CharField(
                default="UGX",
                help_text="ISO 4217 code shown on invoices and fee statements (e.g. UGX, USD).",
                max_length=3,
            ),
        ),
    ]
