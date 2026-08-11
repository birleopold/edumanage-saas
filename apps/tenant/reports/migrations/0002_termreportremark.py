from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0005_subject_role_policies"),
        ("orgsettings", "0006_merge_20260624_1447"),
        ("reports", "0001_initial"),
        ("students", "0005_studentprofile_demographics"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TermReportRemark",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("class_teacher_comment", models.TextField(blank=True)),
                ("head_comment", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "campus",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="term_report_remarks",
                        to="orgsettings.campus",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="term_report_remarks",
                        to="students.studentprofile",
                    ),
                ),
                (
                    "term",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="student_report_remarks",
                        to="academics.academicterm",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_term_report_remarks",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("student__last_name", "student__first_name", "student__student_id"),
            },
        ),
        migrations.AddConstraint(
            model_name="termreportremark",
            constraint=models.UniqueConstraint(
                fields=("student", "term"),
                name="uniq_student_term_report_remark",
            ),
        ),
    ]
