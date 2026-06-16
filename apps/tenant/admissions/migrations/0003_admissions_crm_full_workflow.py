# Generated manually for Admissions CRM full workflow

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("finance", "0001_initial"),
        ("academics", "0001_initial"),
        ("orgsettings", "0001_initial"),
        ("admissions", "0002_public_applications_and_documents"),
    ]

    operations = [
        migrations.AddField(
            model_name="applicant",
            name="custom_responses",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="applicant",
            name="created_admission_invoice",
            field=models.ForeignKey(
                blank=True,
                help_text="Student invoice automatically created during admission conversion, where applicable.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="admission_applicants",
                to="finance.invoice",
            ),
        ),
        migrations.AlterField(
            model_name="applicant",
            name="source",
            field=models.CharField(
                choices=[
                    ("ADMIN", "Admin entry"),
                    ("ONLINE", "Online application"),
                    ("PHONE", "Phone enquiry"),
                    ("WALK_IN", "Walk-in"),
                    ("LEAD", "Converted enquiry"),
                ],
                default="ADMIN",
                max_length=16,
            ),
        ),
        migrations.CreateModel(
            name="AdmissionFormTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("is_default", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("admission_fee_amount", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("admission_fee_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="finance.feeitem")),
                ("campus", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="orgsettings.campus")),
                ("class_group", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="academics.classgroup")),
                ("program", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="academics.program")),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="AdmissionLead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source", models.CharField(choices=[("WEBSITE", "Website"), ("PHONE", "Phone"), ("WALK_IN", "Walk-in"), ("REFERRAL", "Referral"), ("SOCIAL", "Social media"), ("OTHER", "Other")], default="WEBSITE", max_length=16)),
                ("status", models.CharField(choices=[("NEW", "New lead"), ("CONTACTED", "Contacted"), ("FOLLOW_UP", "Follow-up"), ("CONVERTED", "Converted to applicant"), ("LOST", "Lost")], default="NEW", max_length=16)),
                ("learner_name", models.CharField(max_length=180)),
                ("parent_name", models.CharField(blank=True, max_length=180)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=32)),
                ("follow_up_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assigned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("campus", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="orgsettings.campus")),
                ("converted_applicant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="source_leads", to="admissions.applicant")),
                ("interested_class_group", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="academics.classgroup")),
                ("interested_program", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="academics.program")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="AdmissionFormField",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.CharField(max_length=160)),
                ("field_type", models.CharField(choices=[("TEXT", "Short text"), ("TEXTAREA", "Long text"), ("NUMBER", "Number"), ("DATE", "Date"), ("BOOLEAN", "Yes/No"), ("CHOICE", "Choice")], default="TEXT", max_length=16)),
                ("help_text", models.CharField(blank=True, max_length=255)),
                ("choices", models.TextField(blank=True, help_text="For choice fields, enter one option per line.")),
                ("is_required", models.BooleanField(default=False)),
                ("order", models.PositiveIntegerField(default=1)),
                ("is_active", models.BooleanField(default=True)),
                ("template", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="fields", to="admissions.admissionformtemplate")),
            ],
            options={"ordering": ("order", "label")},
        ),
        migrations.CreateModel(
            name="AdmissionAppointment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("appointment_type", models.CharField(choices=[("INTERVIEW", "Interview"), ("TEST", "Admission test"), ("MEETING", "Parent meeting")], default="INTERVIEW", max_length=16)),
                ("status", models.CharField(choices=[("SCHEDULED", "Scheduled"), ("COMPLETED", "Completed"), ("MISSED", "Missed"), ("CANCELLED", "Cancelled")], default="SCHEDULED", max_length=16)),
                ("scheduled_at", models.DateTimeField()),
                ("duration_minutes", models.PositiveIntegerField(default=30)),
                ("location", models.CharField(blank=True, max_length=180)),
                ("score", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("outcome_note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("applicant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="appointments", to="admissions.applicant")),
                ("assigned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("scheduled_at",)},
        ),
        migrations.CreateModel(
            name="ApplicantCommunication",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("channel", models.CharField(choices=[("CALL", "Phone call"), ("SMS", "SMS"), ("WHATSAPP", "WhatsApp"), ("EMAIL", "Email"), ("NOTE", "Internal note")], default="NOTE", max_length=16)),
                ("subject", models.CharField(blank=True, max_length=160)),
                ("message", models.TextField()),
                ("direction", models.CharField(choices=[("INBOUND", "Inbound"), ("OUTBOUND", "Outbound")], default="OUTBOUND", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("applicant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="communications", to="admissions.applicant")),
                ("logged_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="ApplicantPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("method", models.CharField(choices=[("CASH", "Cash"), ("BANK", "Bank"), ("MOBILE", "Mobile money"), ("CARD", "Card")], default="CASH", max_length=16)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("PAID", "Paid"), ("FAILED", "Failed"), ("WAIVED", "Waived")], default="PAID", max_length=16)),
                ("reference", models.CharField(blank=True, max_length=128)),
                ("received_at", models.DateField(default=django.utils.timezone.localdate)),
                ("note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("applicant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="admission_payments", to="admissions.applicant")),
                ("recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-received_at", "-created_at")},
        ),
        migrations.AddIndex(model_name="admissionlead", index=models.Index(fields=["status", "created_at"], name="admissions_lead_status_idx")),
        migrations.AddIndex(model_name="admissionlead", index=models.Index(fields=["follow_up_at"], name="admissions_lead_follow_idx")),
        migrations.AddIndex(model_name="admissionappointment", index=models.Index(fields=["status", "scheduled_at"], name="admissions_appt_status_idx")),
    ]
