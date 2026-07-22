import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def issue_existing_certificate_records(apps, schema_editor):
    ActivityAchievement = apps.get_model("activities", "ActivityAchievement")
    ActivityCertificate = apps.get_model("activities", "ActivityCertificate")
    rows = []
    for achievement in ActivityAchievement.objects.select_related(
        "membership",
        "membership__student",
        "membership__activity",
    ).iterator():
        if achievement.achievement_type != "CERTIFICATE":
            continue
        reference = f"ACT-{achievement.membership.student_id}-{achievement.pk}"
        if ActivityCertificate.objects.filter(reference=reference).exists():
            continue
        rows.append(
            ActivityCertificate(
                achievement_id=achievement.pk,
                reference=reference,
                title=achievement.title,
                statement=(
                    f"Awarded to {achievement.membership.student} for "
                    f"{achievement.title} in {achievement.membership.activity}."
                ),
                snapshot={
                    "achievement_id": achievement.pk,
                    "student_id": achievement.membership.student_id,
                    "activity_id": achievement.membership.activity_id,
                    "achieved_on": achievement.achieved_on.isoformat(),
                    "type": achievement.achievement_type,
                    "level": achievement.level,
                },
            )
        )
    ActivityCertificate.objects.bulk_create(rows, batch_size=500)


class Migration(migrations.Migration):
    dependencies = [
        ("activities", "0003_rename_phase8_session_index"),
        ("students", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ActivityIncident",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("incident_type", models.CharField(choices=[("CONDUCT", "Conduct"), ("INJURY", "Injury"), ("SAFEGUARDING", "Safeguarding"), ("ATTENDANCE", "Attendance"), ("EQUIPMENT", "Equipment or property"), ("TRAVEL", "Travel or trip"), ("OTHER", "Other")], max_length=20)),
                ("severity", models.CharField(choices=[("LOW", "Low"), ("MEDIUM", "Medium"), ("HIGH", "High"), ("CRITICAL", "Critical")], default="LOW", max_length=16)),
                ("status", models.CharField(choices=[("OPEN", "Open"), ("REVIEWING", "Under review"), ("RESOLVED", "Resolved"), ("CLOSED", "Closed")], default="OPEN", max_length=16)),
                ("occurred_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("summary", models.TextField()),
                ("action_taken", models.TextField(blank=True)),
                ("follow_up_at", models.DateTimeField(blank=True, null=True)),
                ("confidential", models.BooleanField(default=False)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="incidents", to="activities.activity")),
                ("recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="activity_incidents_recorded", to=settings.AUTH_USER_MODEL)),
                ("resolved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="activity_incidents_resolved", to=settings.AUTH_USER_MODEL)),
                ("session", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="incidents", to="activities.activitysession")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="activity_incidents", to="students.studentprofile")),
            ],
            options={"ordering": ("-occurred_at",)},
        ),
        migrations.CreateModel(
            name="ActivityCertificate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(max_length=64, unique=True)),
                ("verification_token", models.CharField(editable=False, max_length=64, unique=True)),
                ("title", models.CharField(max_length=200)),
                ("statement", models.TextField()),
                ("issued_at", models.DateTimeField(auto_now_add=True)),
                ("is_revoked", models.BooleanField(default=False)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revocation_reason", models.TextField(blank=True)),
                ("snapshot", models.JSONField(blank=True, default=dict)),
                ("achievement", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="certificate", to="activities.activityachievement")),
                ("issued_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="activity_certificates_issued", to=settings.AUTH_USER_MODEL)),
                ("revoked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="activity_certificates_revoked", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-issued_at",)},
        ),
        migrations.AddIndex(model_name="activityincident", index=models.Index(fields=["student", "status", "severity"], name="activities__student_d6f0ad_idx")),
        migrations.RunPython(issue_existing_certificate_records, migrations.RunPython.noop),
    ]
