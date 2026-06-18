from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orgsettings", "0001_initial"),
        ("parents", "0001_initial"),
        ("students", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[("VIEW", "View"), ("CREATE", "Create"), ("EDIT", "Edit"), ("DELETE", "Delete"), ("EXPORT", "Export"), ("PRINT", "Print"), ("DOWNLOAD", "Download"), ("LOGIN", "Login"), ("LOGOUT", "Logout"), ("PASSWORD", "Password")], db_index=True, max_length=24)),
                ("path", models.CharField(blank=True, max_length=500)),
                ("method", models.CharField(blank=True, max_length=12)),
                ("view_name", models.CharField(blank=True, max_length=180)),
                ("object_label", models.CharField(blank=True, max_length=255)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True)),
                ("query_params", models.JSONField(blank=True, default=dict)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("campus", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="orgsettings.campus")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_events", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="LoginHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username", models.CharField(blank=True, max_length=180)),
                ("status", models.CharField(choices=[("SUCCESS", "Success"), ("FAILED", "Failed"), ("LOGOUT", "Logout")], max_length=16)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True)),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="login_history", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="UserTwoFactorSetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_enabled", models.BooleanField(default=False)),
                ("method", models.CharField(default="EMAIL", max_length=24)),
                ("secret", models.CharField(blank=True, max_length=255)),
                ("backup_codes_hash", models.JSONField(blank=True, default=list)),
                ("last_verified_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="two_factor_setting", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("user__username",)},
        ),
        migrations.CreateModel(
            name="ExportPermission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("module", models.CharField(max_length=80)),
                ("can_export", models.BooleanField(default=False)),
                ("can_print", models.BooleanField(default=False)),
                ("can_download", models.BooleanField(default=False)),
                ("granted_at", models.DateTimeField(auto_now_add=True)),
                ("granted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="granted_export_permissions", to=settings.AUTH_USER_MODEL)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="export_permissions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("module", "user"), "unique_together": {("user", "module")}},
        ),
        migrations.CreateModel(
            name="DataRetentionPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("module", models.CharField(max_length=80, unique=True)),
                ("retention_days", models.PositiveIntegerField(default=2555)),
                ("action_after_retention", models.CharField(default="ARCHIVE", max_length=32)),
                ("is_active", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("module",)},
        ),
    ]
