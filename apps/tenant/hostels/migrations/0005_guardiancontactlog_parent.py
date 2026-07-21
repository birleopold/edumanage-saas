from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("parents", "0001_initial"),
        ("hostels", "0004_phase7_operational_hardening"),
    ]

    operations = [
        migrations.AddField(
            model_name="guardiancontactlog",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                help_text="Linked parent or guardian contacted for this student.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="guardian_contact_logs",
                to="parents.parentprofile",
            ),
        ),
    ]
