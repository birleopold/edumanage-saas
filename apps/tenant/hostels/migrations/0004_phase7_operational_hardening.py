from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("hostels", "0003_rename_phase7_welfare_indexes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WelfareCaseEscalation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "level",
                    models.CharField(
                        choices=[
                            ("NONE", "No escalation"),
                            ("STAFF", "Assigned staff follow-up"),
                            ("SENIOR", "Senior management"),
                            ("SAFEGUARDING", "Safeguarding lead"),
                            ("EMERGENCY", "Emergency response"),
                        ],
                        default="NONE",
                        max_length=20,
                    ),
                ),
                ("response_due_at", models.DateTimeField(blank=True, null=True)),
                ("reason", models.TextField(blank=True)),
                ("guardian_contact_required", models.BooleanField(default=False)),
                ("escalated_at", models.DateTimeField(blank=True, null=True)),
                ("last_reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "escalated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="welfare_case_escalations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "welfare_case",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="operational_escalation",
                        to="hostels.welfarecase",
                    ),
                ),
            ],
            options={"ordering": ("-escalated_at", "-updated_at")},
        ),
        migrations.CreateModel(
            name="GuardianContactLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "purpose",
                    models.CharField(
                        choices=[
                            ("LEAVE_APPROVAL", "Leave approval or confirmation"),
                            ("DEPARTURE", "Departure handover"),
                            ("RETURN", "Return confirmation"),
                            ("ABSENCE", "Roll-call absence follow-up"),
                            ("WELFARE", "Welfare follow-up"),
                            ("EMERGENCY", "Emergency contact"),
                            ("GENERAL", "General boarding contact"),
                        ],
                        default="GENERAL",
                        max_length=24,
                    ),
                ),
                (
                    "method",
                    models.CharField(
                        choices=[
                            ("PHONE", "Phone call"),
                            ("SMS", "SMS"),
                            ("WHATSAPP", "WhatsApp"),
                            ("PORTAL", "Parent portal"),
                            ("IN_PERSON", "In person"),
                            ("EMAIL", "Email"),
                            ("OTHER", "Other"),
                        ],
                        default="PHONE",
                        max_length=16,
                    ),
                ),
                (
                    "outcome",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending response"),
                            ("CONFIRMED", "Confirmed"),
                            ("REACHED", "Reached"),
                            ("MESSAGE_LEFT", "Message left"),
                            ("NO_ANSWER", "No answer"),
                            ("WRONG_NUMBER", "Wrong number"),
                            ("DECLINED", "Declined or not authorised"),
                        ],
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                ("contact_name", models.CharField(blank=True, max_length=150)),
                ("contact_phone", models.CharField(blank=True, max_length=32)),
                ("note", models.TextField(blank=True)),
                ("occurred_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "boarding_leave",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="guardian_contact_logs",
                        to="hostels.boardingleave",
                    ),
                ),
                (
                    "recorded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="guardian_contact_logs_recorded",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "roll_call_entry",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="guardian_contact_logs",
                        to="hostels.hostelrollcallentry",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="guardian_contact_logs",
                        to="students.studentprofile",
                    ),
                ),
                (
                    "welfare_case",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="guardian_contact_logs",
                        to="hostels.welfarecase",
                    ),
                ),
            ],
            options={
                "ordering": ("-occurred_at", "-created_at"),
                "indexes": [
                    models.Index(fields=["student", "occurred_at"], name="hostels_gua_student_4b7267_idx"),
                    models.Index(fields=["outcome", "occurred_at"], name="hostels_gua_outcome_b21f3f_idx"),
                ],
            },
        ),
    ]
