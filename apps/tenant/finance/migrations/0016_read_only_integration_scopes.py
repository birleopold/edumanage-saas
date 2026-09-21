from django.db import migrations


def seed_read_scopes(apps, schema_editor):
    IntegrationScope = apps.get_model("finance", "IntegrationScope")
    for code, name in (
        ("health-read", "Read integration health"),
        ("messages-read", "Read outbound message status"),
        ("webhooks-read", "Read webhook delivery status"),
    ):
        IntegrationScope.objects.get_or_create(
            code=code,
            defaults={"name": name, "description": name},
        )


class Migration(migrations.Migration):
    dependencies = [("finance", "0015_align_clearance_model_state")]
    operations = [migrations.RunPython(seed_read_scopes, migrations.RunPython.noop)]
