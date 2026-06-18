from django.db import migrations, models
import django.db.models.deletion


def seed_scopes(apps, schema_editor):
    Scope = apps.get_model("finance", "IntegrationScope")
    for code, name in [
        ("attendance-write", "Write attendance"),
        ("messages-send", "Send messages"),
        ("payments-write", "Write payments"),
        ("transport-gps", "Vehicle GPS"),
        ("meetings-write", "Create meeting links"),
        ("integrations-admin", "Manage integrations"),
    ]:
        Scope.objects.get_or_create(code=code, defaults={"name": name, "description": name})


class Migration(migrations.Migration):
    dependencies = [("finance", "0005_payment_gateway_events")]

    operations = [
        migrations.CreateModel(
            name="IntegrationProviderConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("provider_type", models.CharField(max_length=32)),
                ("base_url", models.URLField(blank=True, max_length=400)),
                ("client_id", models.CharField(blank=True, max_length=255)),
                ("client_secret", models.CharField(blank=True, max_length=255)),
                ("access_token", models.TextField(blank=True)),
                ("webhook_secret", models.CharField(blank=True, max_length=255)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("last_tested_at", models.DateTimeField(blank=True, null=True)),
                ("last_test_status", models.CharField(blank=True, max_length=32)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("provider_type", "name")},
        ),
        migrations.CreateModel(
            name="IntegrationScope",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(max_length=80, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ("code",)},
        ),
        migrations.CreateModel(
            name="IntegrationApiKeyScope",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("api_key", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="scope_links", to="finance.integrationapikey")),
                ("scope", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="api_key_links", to="finance.integrationscope")),
            ],
            options={"ordering": ("api_key", "scope"), "unique_together": {("api_key", "scope")}},
        ),
        migrations.CreateModel(
            name="IntegrationEventLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(max_length=120)),
                ("direction", models.CharField(default="INBOUND", max_length=16)),
                ("status", models.CharField(default="PENDING", max_length=16)),
                ("external_reference", models.CharField(blank=True, db_index=True, max_length=160)),
                ("request_payload", models.JSONField(blank=True, default=dict)),
                ("response_payload", models.JSONField(blank=True, default=dict)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("api_key", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="integration_events", to="finance.integrationapikey")),
                ("provider", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="event_logs", to="finance.integrationproviderconfig")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.RunPython(seed_scopes, migrations.RunPython.noop),
    ]
