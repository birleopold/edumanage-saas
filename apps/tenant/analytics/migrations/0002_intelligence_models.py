from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("academics", "0003_gradingscale_stream_graderange"),
        ("analytics", "0001_initial"),
        ("students", "0004_studentprofile_stream"),
        ("teachers", "0002_teacherprofile_campus"),
    ]

    operations = [
        migrations.CreateModel(
            name="AnalyticsRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("run_type", models.CharField(choices=[("MANUAL", "Manual"), ("SCHEDULED", "Scheduled")], default="MANUAL", max_length=16)),
                ("status", models.CharField(choices=[("STARTED", "Started"), ("SUCCESS", "Success"), ("FAILED", "Failed")], default="STARTED", max_length=16)),
                ("generated_snapshots", models.PositiveIntegerField(default=0)),
                ("generated_alerts", models.PositiveIntegerField(default=0)),
                ("generated_teacher_metrics", models.PositiveIntegerField(default=0)),
                ("generated_class_reports", models.PositiveIntegerField(default=0)),
                ("error_message", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("term", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="academics.academicterm")),
            ],
            options={"ordering": ("-started_at",)},
        ),
        migrations.CreateModel(
            name="StudentRecommendation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180)),
                ("recommendation", models.TextField()),
                ("priority", models.CharField(default="MEDIUM", max_length=16)),
                ("status", models.CharField(choices=[("OPEN", "Open"), ("IN_PROGRESS", "In progress"), ("COMPLETED", "Completed"), ("DISMISSED", "Dismissed")], default="OPEN", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("alert", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recommendations", to="analytics.atriskalert")),
                ("snapshot", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recommendations", to="analytics.studentperformancesnapshot")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="analytics_recommendations", to="students.studentprofile")),
                ("subject", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="academics.course")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="Intervention",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180)),
                ("plan", models.TextField()),
                ("status", models.CharField(choices=[("PLANNED", "Planned"), ("ACTIVE", "Active"), ("COMPLETED", "Completed"), ("CANCELLED", "Cancelled")], default="PLANNED", max_length=16)),
                ("start_date", models.DateField(default=django.utils.timezone.localdate)),
                ("target_date", models.DateField(blank=True, null=True)),
                ("progress_note", models.TextField(blank=True)),
                ("outcome", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("alert", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="interventions", to="analytics.atriskalert")),
                ("assigned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="interventions", to="teachers.teacherprofile")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="interventions", to="students.studentprofile")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="ReportCardCommentSuggestion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("comment", models.TextField()),
                ("strengths", models.JSONField(blank=True, default=list)),
                ("weak_areas", models.JSONField(blank=True, default=list)),
                ("recommendations", models.JSONField(blank=True, default=list)),
                ("generated_at", models.DateTimeField(auto_now_add=True)),
                ("snapshot", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="analytics.studentperformancesnapshot")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comment_suggestions", to="students.studentprofile")),
                ("term", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="academics.academicterm")),
            ],
            options={"ordering": ("-generated_at",), "unique_together": {("student", "term")}},
        ),
    ]
