from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("announcements", "0002_announcement_is_urgent"),
        ("orgsettings", "0006_merge_20260624_1447"),
    ]
    operations = [
        migrations.AddField(
            model_name="announcement",
            name="campus",
            field=models.ForeignKey(
                blank=True,
                help_text="Leave blank to publish to every campus.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="announcements",
                to="orgsettings.campus",
            ),
        ),
        migrations.AddIndex(
            model_name="announcement",
            index=models.Index(
                fields=["is_active", "audience", "campus"],
                name="announcemen_is_acti_c7e01e_idx",
            ),
        ),
    ]
