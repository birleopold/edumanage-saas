from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("audit", "0001_initial"),
        ("parents", "0001_initial"),
        ("students", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConsentRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("consent_type", models.CharField(choices=[("PRIVACY", "Privacy policy"), ("DATA_PROCESSING", "Data processing"), ("PHOTO", "Photo/media"), ("MEDICAL", "Medical/emergency"), ("COMMUNICATION", "Communication")], max_length=32)),
                ("accepted", models.BooleanField(default=True)),
                ("version", models.CharField(default="1.0", max_length=32)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True)),
                ("note", models.TextField(blank=True)),
                ("recorded_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="consent_records", to="parents.parentprofile")),
                ("student", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="consent_records", to="students.studentprofile")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="consent_records", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-recorded_at",)},
        ),
        migrations.CreateModel(
            name="BackupJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("REQUESTED", "Requested"), ("RUNNING", "Running"), ("SUCCESS", "Success"), ("FAILED", "Failed"), ("RESTORE_TESTED", "Restore tested")], default="REQUESTED", max_length=24)),
                ("file_path", models.CharField(blank=True, max_length=500)),
                ("checksum", models.CharField(blank=True, max_length=128)),
                ("notes", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="SuspiciousLoginAlert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username", models.CharField(blank=True, max_length=180)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("reason", models.CharField(max_length=255)),
                ("status", models.CharField(choices=[("OPEN", "Open"), ("REVIEWED", "Reviewed"), ("DISMISSED", "Dismissed")], default="OPEN", max_length=16)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_login_alerts", to=settings.AUTH_USER_MODEL)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="suspicious_login_alerts", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
    ]
