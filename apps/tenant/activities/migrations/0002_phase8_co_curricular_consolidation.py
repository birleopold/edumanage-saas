# Generated for EduManage Phase 8.

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("activities", "0001_initial"),
        ("hr", "0002_staffprofile_reports_to_staffprofile_staff_category_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ActivityProgramme",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=64, unique=True)),
                ("participation_mode", models.CharField(choices=[("OPEN", "Open participation"), ("SELECTIVE", "Selective participation"), ("TEAM", "Team or squad based")], default="OPEN", max_length=16)),
                ("capacity", models.PositiveIntegerField(blank=True, null=True)),
                ("attendance_required", models.BooleanField(default=True)),
                ("guardian_consent_required", models.BooleanField(default=False)),
                ("medical_clearance_required", models.BooleanField(default=False)),
                ("competitive", models.BooleanField(default=False)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="programme_profile", to="activities.activity")),
            ],
            options={"ordering": ("activity__name",)},
        ),
        migrations.CreateModel(
            name="ActivityGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=128)),
                ("group_type", models.CharField(choices=[("TEAM", "Team"), ("SQUAD", "Squad"), ("ENSEMBLE", "Ensemble"), ("COMMITTEE", "Committee"), ("HOUSE", "House"), ("OTHER", "Other")], default="TEAM", max_length=16)),
                ("capacity", models.PositiveIntegerField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("coach", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="activity_groups_coached", to="hr.staffprofile")),
                ("programme", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="groups", to="activities.activityprogramme")),
            ],
            options={"ordering": ("programme__activity__name", "name")},
        ),
        migrations.CreateModel(
            name="ActivityParticipation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("MEMBER", "Member"), ("CAPTAIN", "Captain"), ("LEADER", "Leader"), ("SECRETARY", "Secretary"), ("TREASURER", "Treasurer"), ("PREFECT", "Prefect"), ("OTHER", "Other")], default="MEMBER", max_length=16)),
                ("guardian_consent_status", models.CharField(choices=[("NOT_REQUIRED", "Not required"), ("PENDING", "Pending"), ("APPROVED", "Approved"), ("DECLINED", "Declined"), ("EXPIRED", "Expired")], default="NOT_REQUIRED", max_length=20)),
                ("guardian_consent_recorded_at", models.DateTimeField(blank=True, null=True)),
                ("medical_clearance_status", models.CharField(choices=[("NOT_REQUIRED", "Not required"), ("PENDING", "Pending"), ("APPROVED", "Approved"), ("DECLINED", "Declined"), ("EXPIRED", "Expired")], default="NOT_REQUIRED", max_length=20)),
                ("medical_clearance_recorded_at", models.DateTimeField(blank=True, null=True)),
                ("emergency_contact_name", models.CharField(blank=True, max_length=150)),
                ("emergency_contact_phone", models.CharField(blank=True, max_length=32)),
                ("notes", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("group", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="participants", to="activities.activitygroup")),
                ("membership", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="participation_profile", to="activities.activitymember")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="activity_participations_updated", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("membership__activity__name", "membership__student__last_name")},
        ),
        migrations.CreateModel(
            name="ActivitySession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("session_type", models.CharField(choices=[("MEETING", "Meeting"), ("TRAINING", "Training"), ("PRACTICE", "Practice"), ("MATCH", "Match"), ("COMPETITION", "Competition"), ("PERFORMANCE", "Performance"), ("SERVICE", "Service activity"), ("TRIP", "Trip"), ("OTHER", "Other")], default="MEETING", max_length=20)),
                ("starts_at", models.DateTimeField()),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                ("location", models.CharField(blank=True, max_length=180)),
                ("attendance_required", models.BooleanField(default=True)),
                ("status", models.CharField(choices=[("DRAFT", "Draft"), ("COMPLETED", "Completed"), ("CANCELLED", "Cancelled"), ("LOCKED", "Locked")], default="DRAFT", max_length=16)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activity", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="programme_sessions", to="activities.activity")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="activity_sessions_created", to=settings.AUTH_USER_MODEL)),
                ("group", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sessions", to="activities.activitygroup")),
            ],
            options={"ordering": ("-starts_at", "activity__name")},
        ),
        migrations.CreateModel(
            name="ActivityAttendance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("UNMARKED", "Not marked"), ("PRESENT", "Present"), ("ABSENT", "Absent"), ("EXCUSED", "Excused"), ("LATE", "Late"), ("INJURED", "Injured or medically excused"), ("ON_DUTY", "On school duty")], default="UNMARKED", max_length=16)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("marked_at", models.DateTimeField(blank=True, null=True)),
                ("marked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="activity_attendance_marked", to=settings.AUTH_USER_MODEL)),
                ("membership", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="session_attendance", to="activities.activitymember")),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attendance_entries", to="activities.activitysession")),
            ],
            options={"ordering": ("membership__student__last_name", "membership__student__first_name")},
        ),
        migrations.CreateModel(
            name="ActivityAchievement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("achievement_type", models.CharField(choices=[("PARTICIPATION", "Participation"), ("LEADERSHIP", "Leadership"), ("AWARD", "Award"), ("MEDAL", "Medal"), ("CERTIFICATE", "Certificate"), ("RECORD", "Record"), ("SERVICE", "Service"), ("OTHER", "Other")], default="PARTICIPATION", max_length=20)),
                ("level", models.CharField(choices=[("SCHOOL", "School"), ("DISTRICT", "District"), ("REGIONAL", "Regional"), ("NATIONAL", "National"), ("INTERNATIONAL", "International"), ("OTHER", "Other")], default="SCHOOL", max_length=20)),
                ("achieved_on", models.DateField(default=django.utils.timezone.localdate)),
                ("position", models.CharField(blank=True, max_length=64)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("membership", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="achievements", to="activities.activitymember")),
                ("recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="activity_achievements_recorded", to=settings.AUTH_USER_MODEL)),
                ("session", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="achievements", to="activities.activitysession")),
            ],
            options={"ordering": ("-achieved_on", "membership__activity__name")},
        ),
        migrations.AddConstraint(
            model_name="activitygroup",
            constraint=models.UniqueConstraint(fields=("programme", "name"), name="uniq_activity_programme_group"),
        ),
        migrations.AddIndex(
            model_name="activitysession",
            index=models.Index(fields=["activity", "status", "starts_at"], name="activities__activit_2e4894_idx"),
        ),
        migrations.AddConstraint(
            model_name="activityattendance",
            constraint=models.UniqueConstraint(fields=("session", "membership"), name="uniq_activity_session_membership"),
        ),
    ]
