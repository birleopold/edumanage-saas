# Generated manually for LMS links, discussions, and progress tracking

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("coursework", "0001_initial"),
        ("students", "0004_studentprofile_stream"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="learningmaterial",
            name="type",
            field=models.CharField(
                choices=[
                    ("HOMEWORK", "Homework"),
                    ("NOTES", "Class Notes"),
                    ("HOLIDAY_PACKAGE", "Holiday Package"),
                    ("VIDEO_LESSON", "Video Lesson"),
                    ("LIVE_CLASS", "Live Class"),
                ],
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="learningmaterial",
            name="external_url",
            field=models.URLField(blank=True, help_text="Optional website, YouTube, Google Drive, or other learning link."),
        ),
        migrations.AddField(
            model_name="learningmaterial",
            name="video_url",
            field=models.URLField(blank=True, help_text="Optional video lesson link."),
        ),
        migrations.AddField(
            model_name="learningmaterial",
            name="meeting_url",
            field=models.URLField(blank=True, help_text="Optional Google Meet, Zoom, or live class link."),
        ),
        migrations.AddField(
            model_name="learningmaterial",
            name="allow_comments",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="assignment",
            name="resource_url",
            field=models.URLField(blank=True, help_text="Optional instruction, reference, video, or live class link."),
        ),
        migrations.AddField(
            model_name="assignment",
            name="allow_comments",
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name="CourseworkComment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.TextField()),
                ("is_teacher_reply", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("assignment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="coursework.assignment")),
                ("material", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="coursework.learningmaterial")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("created_at",)},
        ),
        migrations.CreateModel(
            name="CourseworkProgress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("viewed_at", models.DateTimeField(blank=True, null=True)),
                ("last_downloaded_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("percent_complete", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assignment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="progress_records", to="coursework.assignment")),
                ("material", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="progress_records", to="coursework.learningmaterial")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="coursework_progress", to="students.studentprofile")),
            ],
            options={"ordering": ("-updated_at",)},
        ),
        migrations.AddIndex(model_name="courseworkprogress", index=models.Index(fields=["student", "material"], name="coursework_student_material_idx")),
        migrations.AddIndex(model_name="courseworkprogress", index=models.Index(fields=["student", "assignment"], name="coursework_student_assign_idx")),
    ]
