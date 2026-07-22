import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0013_clearancepolicy_clearanceoverride_and_more"),
        ("institutional", "0002_tertiary_academic_records"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="clearancepolicy",
            name="access_type",
            field=models.CharField(
                choices=[
                    ("ONLINE_EXAM", "Online examination access"),
                    ("PHYSICAL_EXAM", "Physical examination attendance"),
                    ("ASSESSMENT_RESULTS", "Assessment results"),
                    ("ASSESSMENT_REPORT", "Assessment report card"),
                    ("EXAM_RESULTS", "Examination results"),
                    ("EXAM_REPORT", "Examination report card"),
                    ("CANDIDATE_REGISTRATION", "Candidate registration"),
                    ("EXTERNAL_SUBMISSION", "External examination submission"),
                    ("PERMIT_ISSUANCE", "Examination or clearance permit issuance"),
                ],
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="clearancepolicy",
            name="rule_type",
            field=models.CharField(
                choices=[
                    ("FULL_PAYMENT", "Require full payment"),
                    ("MIN_PERCENT", "Require minimum paid percentage"),
                    ("MIN_PAID_AMOUNT", "Require a minimum amount paid"),
                    ("MAX_BALANCE", "Allow up to a maximum outstanding balance"),
                ],
                default="FULL_PAYMENT",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="clearancepolicy",
            name="minimum_paid_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=14,
            ),
        ),
        migrations.AddField(
            model_name="clearancepolicy",
            name="issue_permit_on_success",
            field=models.BooleanField(
                default=False,
                help_text="Issue or refresh a verifiable permit when this clearance decision succeeds.",
            ),
        ),
        migrations.AddField(
            model_name="clearancepolicy",
            name="permit_validity_days",
            field=models.PositiveSmallIntegerField(
                default=30,
                help_text="Validity period used when an automatic permit is issued.",
            ),
        ),
        migrations.AlterField(
            model_name="clearanceoverride",
            name="access_type",
            field=models.CharField(
                choices=[
                    ("ALL", "All clearance-controlled access"),
                    ("ONLINE_EXAM", "Online examination access"),
                    ("PHYSICAL_EXAM", "Physical examination attendance"),
                    ("ASSESSMENT_RESULTS", "Assessment results"),
                    ("ASSESSMENT_REPORT", "Assessment report card"),
                    ("EXAM_RESULTS", "Examination results"),
                    ("EXAM_REPORT", "Examination report card"),
                    ("CANDIDATE_REGISTRATION", "Candidate registration"),
                    ("EXTERNAL_SUBMISSION", "External examination submission"),
                    ("PERMIT_ISSUANCE", "Examination or clearance permit issuance"),
                ],
                default="ALL",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="clearanceoverride",
            name="exception_type",
            field=models.CharField(
                choices=[
                    ("SCHOLARSHIP", "Scholarship"),
                    ("SPONSORSHIP", "Sponsorship"),
                    ("BURSARY", "Bursary"),
                    ("PAYMENT_PLAN", "Approved payment plan"),
                    ("SPECIAL_ARRANGEMENT", "Special arrangement"),
                    ("MANUAL_BURSAR_APPROVAL", "Manual bursar approval"),
                    ("OTHER", "Other authorised exception"),
                ],
                default="OTHER",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="clearanceoverride",
            name="evidence_reference",
            field=models.CharField(
                blank=True,
                help_text="Document, award letter, payment-plan, sponsorship, or approval reference.",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="clearanceoverride",
            name="approved_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=14,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="clearancedecisionlog",
            name="access_type",
            field=models.CharField(
                choices=[
                    ("ONLINE_EXAM", "Online examination access"),
                    ("PHYSICAL_EXAM", "Physical examination attendance"),
                    ("ASSESSMENT_RESULTS", "Assessment results"),
                    ("ASSESSMENT_REPORT", "Assessment report card"),
                    ("EXAM_RESULTS", "Examination results"),
                    ("EXAM_REPORT", "Examination report card"),
                    ("CANDIDATE_REGISTRATION", "Candidate registration"),
                    ("EXTERNAL_SUBMISSION", "External examination submission"),
                    ("PERMIT_ISSUANCE", "Examination or clearance permit issuance"),
                ],
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="clearancedecisionlog",
            name="source",
            field=models.CharField(
                choices=[
                    ("PORTAL", "Portal"),
                    ("ADMIN", "Administrator check"),
                    ("COMMAND", "Command audit"),
                    ("CANDIDATE", "Candidate readiness"),
                    ("PERMIT", "Permit issuance"),
                ],
                default="PORTAL",
                max_length=16,
            ),
        ),
        migrations.CreateModel(
            name="ClearancePermitSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("policy_code", models.CharField(blank=True, max_length=64)),
                ("access_type", models.CharField(max_length=32)),
                ("decision", models.CharField(max_length=16)),
                ("invoiced_amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("paid_amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("outstanding_balance", models.DecimalField(decimal_places=2, max_digits=14)),
                ("paid_percentage", models.DecimalField(decimal_places=2, max_digits=7)),
                ("rule_snapshot", models.JSONField(default=dict)),
                ("override_snapshot", models.JSONField(blank=True, default=dict)),
                ("academic_snapshot", models.JSONField(blank=True, default=dict)),
                ("status", models.CharField(choices=[("ACTIVE", "Active"), ("REVOKED", "Revoked"), ("EXPIRED", "Expired")], default="ACTIVE", max_length=16)),
                ("valid_from", models.DateTimeField()),
                ("valid_until", models.DateTimeField()),
                ("issued_at", models.DateTimeField(auto_now_add=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revocation_reason", models.TextField(blank=True)),
                ("decision_log", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="permit_snapshot", to="finance.clearancedecisionlog")),
                ("issued_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="clearance_permits_issued", to=settings.AUTH_USER_MODEL)),
                ("permit", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="clearance_snapshot", to="institutional.verifiablepermit")),
                ("revoked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="clearance_permits_revoked", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-issued_at",)},
        ),
        migrations.AddIndex(
            model_name="clearancepermitsnapshot",
            index=models.Index(fields=["access_type", "status", "valid_until"], name="finance_cle_access__bde5cf_idx"),
        ),
    ]
