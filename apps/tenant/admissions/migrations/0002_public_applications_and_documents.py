# Generated manually for Phase 1 public admissions workflow

import uuid

import django.db.models.deletion
from django.db import migrations, models

import apps.tenant.admissions.models


def backfill_application_references(apps, schema_editor):
    Applicant = apps.get_model("admissions", "Applicant")
    for applicant in Applicant.objects.filter(application_reference__isnull=True):
        applicant.application_reference = f"APP-LEGACY-{applicant.pk}"
        applicant.save(update_fields=["application_reference"])


class Migration(migrations.Migration):

    dependencies = [
        ("admissions", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="applicant",
            name="application_reference",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Public tracking reference generated when an application is submitted.",
                max_length=32,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="applicant",
            name="guardian_name",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="applicant",
            name="guardian_relationship",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="applicant",
            name="previous_school",
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AddField(
            model_name="applicant",
            name="source",
            field=models.CharField(
                choices=[
                    ("ADMIN", "Admin entry"),
                    ("ONLINE", "Online application"),
                    ("PHONE", "Phone enquiry"),
                    ("WALK_IN", "Walk-in"),
                ],
                default="ADMIN",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="applicant",
            name="submitted_online",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(backfill_application_references, migrations.RunPython.noop),
        migrations.CreateModel(
            name="ApplicantDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("title", models.CharField(default="Supporting document", max_length=120)),
                ("file", models.FileField(upload_to=apps.tenant.admissions.models.applicant_document_upload_to)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "applicant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="admissions.applicant",
                    ),
                ),
            ],
            options={
                "ordering": ("-uploaded_at",),
            },
        ),
        migrations.AddIndex(
            model_name="applicant",
            index=models.Index(fields=["status", "created_at"], name="admissions_status_created_idx"),
        ),
        migrations.AddIndex(
            model_name="applicant",
            index=models.Index(fields=["submitted_online", "created_at"], name="admissions_online_created_idx"),
        ),
    ]
