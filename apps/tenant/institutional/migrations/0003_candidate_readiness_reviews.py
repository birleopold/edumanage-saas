import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0014_clearance_lifecycle_completion"),
        ("institutional", "0002_tertiary_academic_records"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CandidateReadinessReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("READY", "Ready"), ("BLOCKED", "Blocked")], default="BLOCKED", max_length=16)),
                ("target_status", models.CharField(max_length=16)),
                ("checklist_complete", models.BooleanField(default=False)),
                ("photograph_complete", models.BooleanField(default=False)),
                ("continuous_assessment_complete", models.BooleanField(default=False)),
                ("subject_registration_complete", models.BooleanField(default=False)),
                ("finance_clearance_complete", models.BooleanField(default=False)),
                ("blockers", models.JSONField(blank=True, default=list)),
                ("snapshot", models.JSONField(blank=True, default=dict)),
                ("reviewed_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("clearance_log", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="candidate_readiness_reviews", to="finance.clearancedecisionlog")),
                ("dossier", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="readiness_review", to="institutional.candidatedossier")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="candidate_readiness_reviews_completed", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-reviewed_at",)},
        ),
    ]
