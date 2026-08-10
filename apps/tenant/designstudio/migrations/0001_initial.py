# Generated for EduManage Design Studio.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.tenant.designstudio.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("academics", "0001_initial"),
        ("education_frameworks", "0001_initial"),
        ("orgsettings", "0001_initial"),
        ("students", "0006_studentprofile_photo"),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("document_type", models.CharField(choices=[("STUDENT_ID", "Student ID card"), ("REPORT_CARD", "End-of-term report card"), ("TRANSCRIPT", "Academic transcript"), ("LEAVERS_CERTIFICATE", "Leavers certificate"), ("ADMISSION_LETTER", "Admission letter"), ("EXAM_PERMIT", "Examination permit"), ("CERTIFICATE", "Certificate"), ("CUSTOM", "Custom document")], max_length=32)),
                ("description", models.TextField(blank=True)),
                ("active_version_number", models.PositiveIntegerField(blank=True, null=True)),
                ("is_default", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("campus", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="document_templates", to="orgsettings.campus")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_document_templates", to=settings.AUTH_USER_MODEL)),
                ("level", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="document_templates", to="academics.level")),
                ("stage", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="document_templates", to="education_frameworks.educationstage")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_document_templates", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("document_type", "-is_default", "name")},
        ),
        migrations.CreateModel(
            name="DocumentTemplateVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.PositiveIntegerField()),
                ("design", models.JSONField(default=dict)),
                ("page_width_mm", models.DecimalField(decimal_places=2, default=210, max_digits=7)),
                ("page_height_mm", models.DecimalField(decimal_places=2, default=297, max_digits=7)),
                ("background", models.ImageField(blank=True, upload_to=apps.tenant.designstudio.models.design_background_upload_to)),
                ("background_fit", models.CharField(choices=[("COVER", "Cover"), ("CONTAIN", "Contain"), ("STRETCH", "Stretch")], default="COVER", max_length=12)),
                ("status", models.CharField(choices=[("DRAFT", "Draft"), ("IN_REVIEW", "In review"), ("APPROVED", "Approved"), ("ACTIVE", "Active"), ("ARCHIVED", "Archived")], default="DRAFT", max_length=16)),
                ("notes", models.TextField(blank=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("activated_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("activated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="activated_document_template_versions", to=settings.AUTH_USER_MODEL)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_document_template_versions", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_document_template_versions", to=settings.AUTH_USER_MODEL)),
                ("submitted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="submitted_document_template_versions", to=settings.AUTH_USER_MODEL)),
                ("template", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="versions", to="designstudio.documenttemplate")),
            ],
            options={"ordering": ("template", "-number")},
        ),
        migrations.CreateModel(
            name="IssuedDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(max_length=80, unique=True)),
                ("verification_token", models.CharField(default=apps.tenant.designstudio.models.verification_token, editable=False, max_length=80, unique=True)),
                ("status", models.CharField(choices=[("ACTIVE", "Active"), ("REVOKED", "Revoked")], default="ACTIVE", max_length=12)),
                ("data_snapshot", models.JSONField(default=dict)),
                ("pdf_file", models.FileField(blank=True, upload_to=apps.tenant.designstudio.models.issued_document_upload_to)),
                ("issued_at", models.DateTimeField(auto_now_add=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revocation_reason", models.TextField(blank=True)),
                ("academic_term", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="designed_documents", to="academics.academicterm")),
                ("issued_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="issued_designed_documents", to=settings.AUTH_USER_MODEL)),
                ("revoked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="revoked_designed_documents", to=settings.AUTH_USER_MODEL)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="designed_documents", to="students.studentprofile")),
                ("template", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="issued_documents", to="designstudio.documenttemplate")),
                ("version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="issued_documents", to="designstudio.documenttemplateversion")),
            ],
            options={"ordering": ("-issued_at",)},
        ),
        migrations.AddConstraint(
            model_name="documenttemplate",
            constraint=models.UniqueConstraint(fields=("campus", "stage", "level", "document_type", "name"), name="uniq_design_template_scope_name"),
        ),
        migrations.AddConstraint(
            model_name="documenttemplateversion",
            constraint=models.UniqueConstraint(fields=("template", "number"), name="uniq_design_template_version"),
        ),
        migrations.AddIndex(
            model_name="issueddocument",
            index=models.Index(fields=["verification_token", "status"], name="designstudio_verify_idx"),
        ),
    ]
