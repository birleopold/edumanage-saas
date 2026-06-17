# Generated manually for online exam workflow hardening

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("exams", "0001_initial"),
        ("teachers", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="exampaper",
            name="results_published",
            field=models.BooleanField(default=False, help_text="Allow students and parents to view final results."),
        ),
        migrations.AddField(
            model_name="exampaper",
            name="results_published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="exampaper",
            name="report_cards_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="onlineexamattempt",
            name="submitted_by_ip",
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="onlineexamattempt",
            name="user_agent",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="onlineexamattempt",
            name="device_fingerprint",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="onlineexamattempt",
            name="question_order",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="onlineexamattempt",
            name="browser_focus_warnings",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="onlineexamattempt",
            name="last_activity_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="onlineexamattempt",
            name="locked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="onlineexamattempt",
            name="locked_reason",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="studentresponse",
            name="manual_feedback",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="studentresponse",
            name="manually_marked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="studentresponse",
            name="manually_marked_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="teachers.teacherprofile"),
        ),
        migrations.CreateModel(
            name="ExamAntiCheatEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(choices=[("FOCUS_LOST", "Focus lost"), ("TAB_HIDDEN", "Tab hidden"), ("COPY_PASTE", "Copy/paste attempt"), ("FULLSCREEN_EXIT", "Fullscreen exit"), ("AUTO_SUBMIT", "Auto submit"), ("START", "Attempt started"), ("SAVE", "Answers saved"), ("SUBMIT", "Attempt submitted"), ("MANUAL_REVIEW", "Manual review")], max_length=32)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("attempt", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="security_events", to="exams.onlineexamattempt")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddIndex(model_name="examanticheatevent", index=models.Index(fields=["attempt", "event_type", "created_at"], name="exams_anticheat_idx")),
    ]
