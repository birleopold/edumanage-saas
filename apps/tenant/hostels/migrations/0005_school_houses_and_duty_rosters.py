import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("hostels", "0004_phase7_operational_hardening"),
        ("hr", "0002_staffprofile_reports_to_staffprofile_staff_category_and_more"),
        ("students", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SchoolHouse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=128)),
                ("code", models.CharField(max_length=32)),
                ("motto", models.CharField(blank=True, max_length=180)),
                ("identity_label", models.CharField(blank=True, help_text="Optional colour, symbol, saint, founder, or local identity label.", max_length=64)),
                ("capacity", models.PositiveIntegerField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("campus", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="school_houses", to="orgsettings.campus")),
            ],
            options={"ordering": ("campus__name", "name")},
        ),
        migrations.CreateModel(
            name="HouseMembership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("starts_on", models.DateField(default=django.utils.timezone.localdate)),
                ("ends_on", models.DateField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assigned_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="house_memberships_assigned", to=settings.AUTH_USER_MODEL)),
                ("house", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="memberships", to="hostels.schoolhouse")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="house_memberships", to="students.studentprofile")),
            ],
            options={"ordering": ("house__name", "student__last_name", "student__first_name")},
        ),
        migrations.CreateModel(
            name="HouseStaffAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("HOUSE_MASTER", "House master"), ("HOUSE_MISTRESS", "House mistress"), ("MATRON", "Matron"), ("WARDEN", "Warden"), ("DEPUTY", "Deputy house staff"), ("PATRON", "House patron"), ("RESIDENT_TUTOR", "Resident tutor"), ("OTHER", "Other house responsibility")], max_length=24)),
                ("starts_on", models.DateField(default=django.utils.timezone.localdate)),
                ("ends_on", models.DateField(blank=True, null=True)),
                ("is_primary", models.BooleanField(default=False)),
                ("is_resident", models.BooleanField(default=False)),
                ("duty_phone", models.CharField(blank=True, max_length=32)),
                ("responsibilities", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assigned_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="house_staff_assignments_created", to=settings.AUTH_USER_MODEL)),
                ("house", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="staff_assignments", to="hostels.schoolhouse")),
                ("staff", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="house_assignments", to="hr.staffprofile")),
            ],
            options={"ordering": ("house__name", "role", "staff__last_name")},
        ),
        migrations.CreateModel(
            name="BoardingDutyRoster",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("shift", models.CharField(choices=[("MORNING", "Morning duty"), ("DAY", "Day duty"), ("EVENING", "Evening duty"), ("NIGHT", "Night duty"), ("WEEKEND", "Weekend duty"), ("CUSTOM", "Custom duty")], default="EVENING", max_length=16)),
                ("duty_starts_at", models.DateTimeField()),
                ("duty_ends_at", models.DateTimeField()),
                ("duty_area", models.CharField(blank=True, max_length=160)),
                ("status", models.CharField(choices=[("SCHEDULED", "Scheduled"), ("ON_DUTY", "On duty"), ("COMPLETED", "Completed"), ("MISSED", "Missed"), ("CANCELLED", "Cancelled")], default="SCHEDULED", max_length=16)),
                ("instructions", models.TextField(blank=True)),
                ("incidents_summary", models.TextField(blank=True)),
                ("handover_note", models.TextField(blank=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assignment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="duty_rosters", to="hostels.housestaffassignment")),
                ("completed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="boarding_duties_completed", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="boarding_duties_created", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-duty_starts_at", "assignment__house__name")},
        ),
        migrations.AddConstraint(model_name="schoolhouse", constraint=models.UniqueConstraint(fields=("campus", "code"), name="uniq_campus_school_house_code")),
        migrations.AddConstraint(model_name="schoolhouse", constraint=models.UniqueConstraint(fields=("campus", "name"), name="uniq_campus_school_house_name")),
        migrations.AddConstraint(model_name="housemembership", constraint=models.UniqueConstraint(condition=models.Q(("is_active", True)), fields=("student",), name="uniq_active_house_membership_student")),
        migrations.AddConstraint(model_name="housestaffassignment", constraint=models.UniqueConstraint(condition=models.Q(("is_active", True)), fields=("house", "staff", "role"), name="uniq_active_house_staff_role")),
        migrations.AddIndex(model_name="boardingdutyroster", index=models.Index(fields=["status", "duty_starts_at", "duty_ends_at"], name="hostels_boa_status_1e8424_idx")),
    ]
