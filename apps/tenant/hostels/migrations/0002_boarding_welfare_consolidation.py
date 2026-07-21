from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("discipline", "0001_initial"),
        ("hostels", "0001_initial"),
        ("orgsettings", "0006_merge_20260624_1447"),
        ("sickbay", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BoardingProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "boarding_status",
                    models.CharField(
                        choices=[
                            ("DAY", "Day learner"),
                            ("BOARDER", "Full boarder"),
                            ("WEEKLY", "Weekly boarder"),
                            ("FLEXIBLE", "Flexible boarding arrangement"),
                        ],
                        default="DAY",
                        max_length=16,
                    ),
                ),
                ("primary_guardian_name", models.CharField(blank=True, max_length=150)),
                ("primary_guardian_phone", models.CharField(blank=True, max_length=32)),
                ("alternate_contact_name", models.CharField(blank=True, max_length=150)),
                ("alternate_contact_phone", models.CharField(blank=True, max_length=32)),
                ("authorised_pickup_people", models.JSONField(blank=True, default=list)),
                ("dietary_requirements", models.TextField(blank=True)),
                ("accessibility_support", models.TextField(blank=True)),
                (
                    "safeguarding_note",
                    models.TextField(
                        blank=True,
                        help_text="Sensitive boarding or safeguarding information. Limit access to authorised staff.",
                    ),
                ),
                ("general_note", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "student",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="boarding_profile",
                        to="students.studentprofile",
                    ),
                ),
            ],
            options={"ordering": ("student__last_name", "student__first_name")},
        ),
        migrations.CreateModel(
            name="BoardingLeave",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "leave_type",
                    models.CharField(
                        choices=[
                            ("HOME", "Home leave"),
                            ("MEDICAL", "Medical leave"),
                            ("ACTIVITY", "School activity"),
                            ("EMERGENCY", "Emergency leave"),
                            ("OTHER", "Other"),
                        ],
                        default="HOME",
                        max_length=16,
                    ),
                ),
                ("expected_departure_at", models.DateTimeField()),
                ("expected_return_at", models.DateTimeField()),
                ("destination", models.CharField(blank=True, max_length=200)),
                ("reason", models.TextField(blank=True)),
                ("guardian_name", models.CharField(blank=True, max_length=150)),
                ("guardian_phone", models.CharField(blank=True, max_length=32)),
                ("handover_to", models.CharField(blank=True, max_length=150)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending approval"),
                            ("APPROVED", "Approved"),
                            ("DEPARTED", "Departed"),
                            ("RETURNED", "Returned"),
                            ("REJECTED", "Rejected"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        default="PENDING",
                        max_length=16,
                    ),
                ),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("departed_at", models.DateTimeField(blank=True, null=True)),
                ("returned_at", models.DateTimeField(blank=True, null=True)),
                ("return_note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="boarding_leaves_approved",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "bed_allocation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="boarding_leaves",
                        to="hostels.bedallocation",
                    ),
                ),
                (
                    "linked_sickbay_visit",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="boarding_leaves",
                        to="sickbay.sickbayvisit",
                    ),
                ),
                (
                    "recorded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="boarding_leaves_recorded",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="boarding_leaves",
                        to="students.studentprofile",
                    ),
                ),
            ],
            options={
                "ordering": ("-expected_departure_at", "-created_at"),
                "indexes": [
                    models.Index(fields=["student", "status"], name="hostels_boa_student_18a627_idx"),
                    models.Index(fields=["status", "expected_return_at"], name="hostels_boa_status_da9b47_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="HostelRollCall",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("roll_call_date", models.DateField(default=django.utils.timezone.localdate)),
                (
                    "shift",
                    models.CharField(
                        choices=[
                            ("MORNING", "Morning"),
                            ("EVENING", "Evening"),
                            ("NIGHT", "Night"),
                            ("CUSTOM", "Custom"),
                        ],
                        default="EVENING",
                        max_length=16,
                    ),
                ),
                ("taken_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "status",
                    models.CharField(
                        choices=[("DRAFT", "Draft"), ("COMPLETED", "Completed"), ("LOCKED", "Locked")],
                        default="DRAFT",
                        max_length=16,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "hostel",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="roll_calls",
                        to="hostels.hostel",
                    ),
                ),
                (
                    "recorded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="hostel_roll_calls_recorded",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-roll_call_date", "hostel__name", "shift"),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("hostel", "roll_call_date", "shift"),
                        name="uniq_hostel_roll_call_shift",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="WelfareCase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("HEALTH", "Health"),
                            ("SAFEGUARDING", "Safeguarding"),
                            ("DISCIPLINE", "Discipline"),
                            ("BOARDING", "Boarding"),
                            ("EMOTIONAL", "Emotional wellbeing"),
                            ("FAMILY", "Family or home"),
                            ("ACADEMIC", "Academic support"),
                            ("OTHER", "Other"),
                        ],
                        default="OTHER",
                        max_length=24,
                    ),
                ),
                (
                    "severity",
                    models.CharField(
                        choices=[("LOW", "Low"), ("MEDIUM", "Medium"), ("HIGH", "High"), ("CRITICAL", "Critical")],
                        default="MEDIUM",
                        max_length=16,
                    ),
                ),
                ("title", models.CharField(max_length=200)),
                ("summary", models.TextField(blank=True)),
                ("confidential", models.BooleanField(default=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("OPEN", "Open"),
                            ("MONITORING", "Monitoring"),
                            ("REFERRED", "Referred"),
                            ("RESOLVED", "Resolved"),
                            ("CLOSED", "Closed"),
                        ],
                        default="OPEN",
                        max_length=16,
                    ),
                ),
                ("due_date", models.DateField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("resolution_summary", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "assigned_to",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="welfare_cases_assigned",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "campus",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="welfare_cases",
                        to="orgsettings.campus",
                    ),
                ),
                (
                    "linked_bed_allocation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="welfare_cases",
                        to="hostels.bedallocation",
                    ),
                ),
                (
                    "linked_discipline_incident",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="welfare_cases",
                        to="discipline.incident",
                    ),
                ),
                (
                    "linked_sickbay_visit",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="welfare_cases",
                        to="sickbay.sickbayvisit",
                    ),
                ),
                (
                    "opened_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="welfare_cases_opened",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="welfare_cases",
                        to="students.studentprofile",
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at",),
                "indexes": [
                    models.Index(fields=["student", "status"], name="hostels_wel_student_4d92e9_idx"),
                    models.Index(fields=["campus", "status", "severity"], name="hostels_wel_campus__07bcf1_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="HostelRollCallEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "presence",
                    models.CharField(
                        choices=[
                            ("UNMARKED", "Not marked"),
                            ("PRESENT", "Present"),
                            ("ABSENT", "Absent"),
                            ("EXCUSED", "Excused"),
                            ("SICK", "Sick"),
                            ("ON_LEAVE", "On approved leave"),
                        ],
                        default="UNMARKED",
                        max_length=16,
                    ),
                ),
                ("note", models.CharField(blank=True, max_length=255)),
                ("checked_at", models.DateTimeField(auto_now=True)),
                (
                    "bed_allocation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="roll_call_entries",
                        to="hostels.bedallocation",
                    ),
                ),
                (
                    "boarding_leave",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="roll_call_entries",
                        to="hostels.boardingleave",
                    ),
                ),
                (
                    "roll_call",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="entries",
                        to="hostels.hostelrollcall",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hostel_roll_call_entries",
                        to="students.studentprofile",
                    ),
                ),
            ],
            options={
                "ordering": ("student__last_name", "student__first_name"),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("roll_call", "student"),
                        name="uniq_roll_call_student",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="WelfareCaseAction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "action_type",
                    models.CharField(
                        choices=[
                            ("NOTE", "Note"),
                            ("FOLLOW_UP", "Follow-up"),
                            ("CONTACT", "Parent or guardian contact"),
                            ("REFERRAL", "Referral"),
                            ("ESCALATION", "Escalation"),
                            ("RESOLUTION", "Resolution"),
                        ],
                        default="NOTE",
                        max_length=16,
                    ),
                ),
                ("note", models.TextField()),
                ("next_follow_up_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "performed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="welfare_case_actions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "welfare_case",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="actions",
                        to="hostels.welfarecase",
                    ),
                ),
            ],
            options={"ordering": ("created_at",)},
        ),
    ]
