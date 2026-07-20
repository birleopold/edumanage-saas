from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


TYPE_TEMPLATES = (
    ("QUIZ", "Quiz", "CONTINUOUS", "Short formative assessment or knowledge check.", {}),
    ("TEST", "Test", "CONTINUOUS", "General classroom or topic test.", {}),
    ("ASSIGNMENT", "Assignment", "COURSEWORK", "Individual or group assignment.", {}),
    ("PROJECT", "Project", "PROJECT", "Extended project, investigation or portfolio activity.", {}),
    ("PRACTICAL", "Practical", "PRACTICAL", "Laboratory, workshop, studio or field practical.", {}),
    ("COURSEWORK", "Coursework", "COURSEWORK", "Combined coursework or continuous-assessment component.", {}),
    ("ORAL", "Oral or Presentation", "ORAL", "Oral examination, presentation, recital or demonstration.", {}),
    ("EXAM", "Examination", "EXAMINATION", "Formal internal or external examination component.", {}),
    ("BOT", "Beginning of Term Test", "CONTINUOUS", "Uganda-oriented beginning-of-term assessment.", {"UG": "BOT"}),
    ("MOT", "Mid-Term Test", "CONTINUOUS", "Uganda-oriented mid-term assessment.", {"UG": "MOT"}),
    ("EOT", "End of Term Examination", "EXAMINATION", "Uganda-oriented end-of-term examination.", {"UG": "EOT"}),
    ("AOI", "Activity of Integration", "COMPETENCY", "Competency-based activity integrating knowledge, skills and values.", {"UG": "AOI"}),
)


def seed_assessment_types(apps, schema_editor):
    AssessmentType = apps.get_model("assessments", "AssessmentType")
    for code, name, kind, description, local_aliases in TYPE_TEMPLATES:
        AssessmentType.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "kind": kind,
                "description": description,
                "local_aliases": local_aliases,
                "is_system": True,
                "is_active": True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0003_gradingscale_stream_graderange"),
        ("assessments", "0002_assessmentscore_report_comment_and_more"),
        ("education_frameworks", "0001_initial"),
        ("orgsettings", "0006_merge_20260624_1447"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssessmentType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=32, unique=True)),
                ("name", models.CharField(max_length=96)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("CONTINUOUS", "Continuous Assessment"),
                            ("EXAMINATION", "Examination"),
                            ("COURSEWORK", "Coursework"),
                            ("PROJECT", "Project"),
                            ("PRACTICAL", "Practical"),
                            ("COMPETENCY", "Competency Activity"),
                            ("ORAL", "Oral or Presentation"),
                            ("OTHER", "Other"),
                        ],
                        default="CONTINUOUS",
                        max_length=24,
                    ),
                ),
                ("description", models.TextField(blank=True)),
                ("local_aliases", models.JSONField(blank=True, default=dict)),
                (
                    "default_max_score",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=6,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.01"))],
                    ),
                ),
                (
                    "default_weight",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=6,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.00"))],
                    ),
                ),
                ("is_system", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("kind", "name")},
        ),
        migrations.CreateModel(
            name="AssessmentWeightingScheme",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=48, unique=True)),
                ("name", models.CharField(max_length=128)),
                ("description", models.TextField(blank=True)),
                (
                    "total_weight",
                    models.DecimalField(
                        decimal_places=2,
                        default=100,
                        max_digits=7,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.01"))],
                    ),
                ),
                (
                    "missing_score_policy",
                    models.CharField(
                        choices=[
                            ("IGNORE", "Ignore missing assessments and normalize completed work"),
                            ("ZERO", "Treat missing required assessments as zero"),
                            ("INCOMPLETE", "Mark result incomplete until required assessments are entered"),
                        ],
                        default="INCOMPLETE",
                        max_length=16,
                    ),
                ),
                (
                    "normalize_to_total",
                    models.BooleanField(
                        default=True,
                        help_text="Normalize completed component weights to a percentage when the policy permits it.",
                    ),
                ),
                ("priority", models.IntegerField(default=0)),
                ("is_default", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "academic_term",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assessment_weighting_schemes", to="academics.academicterm"),
                ),
                (
                    "campus",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assessment_weighting_schemes", to="orgsettings.campus"),
                ),
                (
                    "program",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assessment_weighting_schemes", to="academics.program"),
                ),
                (
                    "stage",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assessment_weighting_schemes", to="education_frameworks.educationstage"),
                ),
            ],
            options={"ordering": ("-priority", "-is_default", "name")},
        ),
        migrations.CreateModel(
            name="AssessmentWeightingComponent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "weight",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=7,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.01"))],
                    ),
                ),
                (
                    "aggregation_method",
                    models.CharField(
                        choices=[
                            ("AVERAGE", "Average completed assessments"),
                            ("BEST", "Best completed assessment"),
                            ("LATEST", "Latest completed assessment"),
                        ],
                        default="AVERAGE",
                        max_length=16,
                    ),
                ),
                ("minimum_occurrences", models.PositiveSmallIntegerField(default=1)),
                ("maximum_occurrences", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("drop_lowest_count", models.PositiveSmallIntegerField(default=0)),
                ("is_required", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                ("order", models.PositiveSmallIntegerField(default=1)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "assessment_type",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="weighting_components", to="assessments.assessmenttype"),
                ),
                (
                    "scheme",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="components", to="assessments.assessmentweightingscheme"),
                ),
            ],
            options={"ordering": ("scheme", "order", "assessment_type__name")},
        ),
        migrations.AddField(
            model_name="assessment",
            name="assessment_type",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assessments", to="assessments.assessmenttype"),
        ),
        migrations.AddField(
            model_name="assessment",
            name="weighting_component",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assessments", to="assessments.assessmentweightingcomponent"),
        ),
        migrations.AddConstraint(
            model_name="assessmentweightingcomponent",
            constraint=models.UniqueConstraint(fields=("scheme", "assessment_type"), name="uniq_scheme_assessment_type"),
        ),
        migrations.RunPython(seed_assessment_types, migrations.RunPython.noop),
    ]
