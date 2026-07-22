import django.db.models.deletion
import django.utils.timezone
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0003_gradingscale_stream_graderange"),
        ("institutional", "0001_initial"),
        ("students", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AcademicAttemptPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("replacement_mode", models.CharField(choices=[("LATEST", "Latest completed attempt replaces earlier attempts"), ("BEST", "Best completed attempt counts toward GPA"), ("ORIGINAL", "Original attempt remains in GPA unless manually excluded")], default="LATEST", max_length=16)),
                ("maximum_attempts", models.PositiveSmallIntegerField(default=3)),
                ("supplementary_max_percentage", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("pass_grade_point", models.DecimalField(decimal_places=2, default=Decimal("2.00"), max_digits=5)),
                ("probation_cgpa", models.DecimalField(decimal_places=2, default=Decimal("2.00"), max_digits=5)),
                ("dismissal_cgpa", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("priority", models.IntegerField(default=0)),
                ("is_default", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("campus", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="academic_attempt_policies", to="orgsettings.campus")),
                ("level", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="academic_attempt_policies", to="academics.level")),
                ("program", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="academic_attempt_policies", to="academics.program")),
            ],
            options={"ordering": ("-priority", "-is_default", "name")},
        ),
        migrations.CreateModel(
            name="SemesterRegistration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("REGISTERED", "Registered"), ("ACTIVE", "Active"), ("COMPLETED", "Completed"), ("WITHDRAWN", "Withdrawn"), ("CANCELLED", "Cancelled")], default="REGISTERED", max_length=16)),
                ("registration_reference", models.CharField(blank=True, max_length=96)),
                ("registered_on", models.DateField(default=django.utils.timezone.localdate)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("academic_term", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="semester_registrations", to="academics.academicterm")),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="semester_registrations_approved", to=settings.AUTH_USER_MODEL)),
                ("program", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="semester_registrations", to="academics.program")),
                ("registered_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="semester_registrations_recorded", to=settings.AUTH_USER_MODEL)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="semester_registrations", to="students.studentprofile")),
            ],
            options={"ordering": ("-academic_term__year__name", "-academic_term__order", "student__last_name")},
        ),
        migrations.CreateModel(
            name="CourseAttempt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("attempt_number", models.PositiveSmallIntegerField(default=1)),
                ("attempt_type", models.CharField(choices=[("ORDINARY", "Ordinary attempt"), ("RETAKE", "Retake"), ("SUPPLEMENTARY", "Supplementary examination"), ("REPEAT", "Repeated course")], default="ORDINARY", max_length=20)),
                ("status", models.CharField(choices=[("REGISTERED", "Registered"), ("IN_PROGRESS", "In progress"), ("COMPLETED", "Completed"), ("WITHDRAWN", "Withdrawn"), ("DEFERRED", "Deferred")], default="REGISTERED", max_length=16)),
                ("score", models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True)),
                ("percentage", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("grade", models.CharField(blank=True, max_length=16)),
                ("grade_point", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("credits", models.DecimalField(decimal_places=2, default=Decimal("1.00"), max_digits=6)),
                ("counts_toward_gpa", models.BooleanField(default=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="course_attempts_approved", to=settings.AUTH_USER_MODEL)),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="academic_attempts", to="academics.course")),
                ("offering", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="academic_attempts", to="academics.courseoffering")),
                ("registration", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attempts", to="institutional.semesterregistration")),
                ("registered_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="course_attempts_registered", to=settings.AUTH_USER_MODEL)),
                ("replaced_attempt", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="replacement_attempts", to="institutional.courseattempt")),
            ],
            options={"ordering": ("registration__academic_term__year__name", "registration__academic_term__order", "course__name", "attempt_number")},
        ),
        migrations.CreateModel(
            name="AcademicStanding",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("semester_gpa", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=5)),
                ("cumulative_gpa", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=5)),
                ("attempted_credits", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=8)),
                ("earned_credits", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=8)),
                ("standing", models.CharField(choices=[("GOOD", "Good standing"), ("WARNING", "Academic warning"), ("PROBATION", "Academic probation"), ("DISMISSED", "Dismissed"), ("COMPLETED", "Programme completed")], default="GOOD", max_length=16)),
                ("progression_decision", models.CharField(blank=True, max_length=96)),
                ("snapshot", models.JSONField(blank=True, default=dict)),
                ("calculated_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("academic_term", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="academic_standings", to="academics.academicterm")),
                ("calculated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="academic_standings_calculated", to=settings.AUTH_USER_MODEL)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="academic_standings", to="students.studentprofile")),
            ],
            options={"ordering": ("-academic_term__year__name", "-academic_term__order")},
        ),
        migrations.AddConstraint(model_name="semesterregistration", constraint=models.UniqueConstraint(fields=("student", "academic_term"), name="uniq_student_semester_registration")),
        migrations.AddConstraint(model_name="courseattempt", constraint=models.UniqueConstraint(fields=("registration", "course", "attempt_number"), name="uniq_semester_course_attempt_number")),
        migrations.AddIndex(model_name="courseattempt", index=models.Index(fields=["course", "attempt_type", "status"], name="institution_course__ee9fbc_idx")),
        migrations.AddConstraint(model_name="academicstanding", constraint=models.UniqueConstraint(fields=("student", "academic_term"), name="uniq_student_term_academic_standing")),
    ]
