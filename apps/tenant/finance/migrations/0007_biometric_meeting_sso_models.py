from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("academics", "0001_initial"),
        ("attendance", "0001_initial"),
        ("finance", "0006_integration_provider_scopes"),
        ("orgsettings", "0001_initial"),
        ("students", "0004_studentprofile_stream"),
    ]

    operations = [
        migrations.CreateModel(
            name="BiometricDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("device_code", models.CharField(max_length=120, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
                ("campus", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="orgsettings.campus")),
                ("provider", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="finance.integrationproviderconfig")),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="BiometricAttendanceEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("external_person_id", models.CharField(blank=True, max_length=120)),
                ("event_time", models.DateTimeField(default=django.utils.timezone.now)),
                ("raw_payload", models.JSONField(blank=True, default=dict)),
                ("processed", models.BooleanField(default=False)),
                ("error_message", models.TextField(blank=True)),
                ("attendance_entry", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="attendance.attendanceentry")),
                ("device", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="events", to="finance.biometricdevice")),
                ("offering", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="academics.courseoffering")),
                ("student", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="biometric_events", to="students.studentprofile")),
            ],
            options={"ordering": ("-event_time",)},
        ),
        migrations.CreateModel(
            name="MeetingSessionLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider_type", models.CharField(max_length=32)),
                ("title", models.CharField(max_length=180)),
                ("meeting_url", models.URLField(max_length=500)),
                ("external_meeting_id", models.CharField(blank=True, max_length=160)),
                ("starts_at", models.DateTimeField(blank=True, null=True)),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("offering", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="meeting_links", to="academics.courseoffering")),
                ("provider", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="finance.integrationproviderconfig")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="SSOLoginProvider",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider_type", models.CharField(max_length=32)),
                ("name", models.CharField(max_length=120)),
                ("client_id", models.CharField(max_length=255)),
                ("client_secret", models.CharField(blank=True, max_length=255)),
                ("authorization_url", models.URLField(max_length=400)),
                ("token_url", models.URLField(blank=True, max_length=400)),
                ("userinfo_url", models.URLField(blank=True, max_length=400)),
                ("scopes", models.CharField(default="openid email profile", max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ("provider_type", "name")},
        ),
    ]
