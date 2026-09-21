from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("finance", "0016_read_only_integration_scopes")]
    operations = [
        migrations.AddField(
            model_name="integrationapikey",
            name="allowed_ip_addresses",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Optional exact client IP allowlist. Leave empty to allow any address.",
            ),
        ),
        migrations.AddField(
            model_name="integrationapikey",
            name="expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
