from django.db import migrations, models
import django.db.models.deletion


NEUTRAL_TERMINOLOGY = {
    "institution": "Institution",
    "school": "School",
    "learner": "Student",
    "guardian": "Parent or Guardian",
    "teacher": "Teacher",
    "class": "Class",
    "stream": "Stream",
    "subject": "Subject",
    "course": "Course",
    "course_unit": "Course Unit",
    "academic_period": "Academic Period",
    "term": "Term",
    "semester": "Semester",
    "assessment": "Assessment",
    "exam": "Exam",
    "coursework": "Coursework",
    "assignment": "Assignment",
    "report_card": "Report Card",
    "candidate": "Candidate",
    "external_exam": "External Exam",
    "boarding": "Boarding and Welfare",
    "hostel": "Hostel or Residence",
    "house": "House",
    "fees": "Fees",
    "clearance": "Assessment Clearance",
    "activities": "Clubs, Sports and Activities",
}

UGANDA_TERMINOLOGY = {
    **NEUTRAL_TERMINOLOGY,
    "institution": "School or Institution",
    "learner": "Learner",
    "external_exam": "UNEB or External Exam",
    "boarding": "Boarding and Student Welfare",
    "clearance": "Exam and Fees Clearance",
}

STAGES = (
    ("ECD", "Early Childhood Education", "ECD / Pre-Primary", 10, "TERM", "Nursery, kindergarten, pre-primary and early-years programmes."),
    ("PRIMARY", "Primary Education", "Primary", 20, "TERM", "Primary or elementary education levels."),
    ("LOWER_SECONDARY", "Lower Secondary Education", "O-Level / Lower Secondary", 30, "TERM", "Lower-secondary programmes, including Uganda O-Level."),
    ("UPPER_SECONDARY", "Upper Secondary Education", "A-Level / Upper Secondary", 40, "TERM", "Upper-secondary programmes, including Uganda A-Level."),
    ("TERTIARY", "Tertiary and Vocational Education", "Tertiary / TVET", 50, "SEMESTER", "Certificate, diploma, vocational and technical programmes."),
    ("UNIVERSITY", "University Education", "University", 60, "SEMESTER", "Undergraduate, postgraduate and university programmes."),
    ("OTHER", "Other Education Programme", "Other / Custom", 90, "CUSTOM", "Flexible stage for programmes outside the standard templates."),
)

UGANDA_STAGE_SETTINGS = {
    "ECD": ("ECD / Pre-Primary", "Class", "Learning Area", "Term", "Progress Report", False, {}),
    "PRIMARY": ("Primary", "Class", "Subject", "Term", "Report Card", True, {"candidate_levels": ["P7"], "external_exam": "PLE"}),
    "LOWER_SECONDARY": ("O-Level / Lower Secondary", "Class", "Subject", "Term", "Report Card", True, {"candidate_levels": ["S4"], "external_exam": "UCE"}),
    "UPPER_SECONDARY": ("A-Level / Upper Secondary", "Class", "Subject", "Term", "Report Card", True, {"candidate_levels": ["S6"], "external_exam": "UACE"}),
    "TERTIARY": ("Tertiary / TVET", "Year or Cohort", "Course Unit", "Semester", "Academic Report", False, {}),
    "UNIVERSITY": ("University", "Year or Cohort", "Course Unit", "Semester", "Academic Transcript", False, {}),
    "OTHER": ("Other / Custom", "Group", "Course", "Academic Period", "Academic Report", False, {}),
}


def seed_framework_templates(apps, schema_editor):
    EducationStage = apps.get_model("education_frameworks", "EducationStage")
    AcademicFramework = apps.get_model("education_frameworks", "AcademicFramework")
    FrameworkStage = apps.get_model("education_frameworks", "FrameworkStage")

    stages = {}
    for code, name, local_name, order, period_type, description in STAGES:
        stage, _ = EducationStage.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "local_name": local_name,
                "order": order,
                "default_period_type": period_type,
                "description": description,
                "is_system": True,
                "is_active": True,
            },
        )
        stages[code] = stage

    uganda, _ = AcademicFramework.objects.update_or_create(
        code="UG-NATIONAL",
        defaults={
            "name": "Uganda National Curriculum",
            "country_code": "UG",
            "description": "Configurable Uganda-oriented template with international-neutral core labels.",
            "default_terminology": UGANDA_TERMINOLOGY,
            "default_settings": {
                "assessment_aliases": {
                    "BOT": "Beginning of Term Test",
                    "MOT": "Mid-Term Test",
                    "EOT": "End of Term Examination",
                    "AOI": "Activity of Integration",
                },
                "external_exam_aliases": ["PLE", "UCE", "UACE", "UNEB"],
                "performing_arts_alias": "MDD",
            },
            "is_system_template": True,
            "is_active": True,
        },
    )
    international, _ = AcademicFramework.objects.update_or_create(
        code="INTERNATIONAL-CUSTOM",
        defaults={
            "name": "International or Custom Curriculum",
            "country_code": "",
            "description": "Neutral template for international, private and custom curricula.",
            "default_terminology": NEUTRAL_TERMINOLOGY,
            "default_settings": {},
            "is_system_template": True,
            "is_active": True,
        },
    )

    for code, stage in stages.items():
        local_name, class_label, subject_label, period_label, report_label, candidate_class, settings = UGANDA_STAGE_SETTINGS[code]
        FrameworkStage.objects.update_or_create(
            framework=uganda,
            stage=stage,
            defaults={
                "local_name": local_name,
                "class_label": class_label,
                "subject_label": subject_label,
                "period_label": period_label,
                "report_label": report_label,
                "candidate_class": candidate_class,
                "settings": settings,
                "is_active": True,
            },
        )
        FrameworkStage.objects.update_or_create(
            framework=international,
            stage=stage,
            defaults={
                "local_name": stage.name,
                "class_label": "Year or Cohort" if code in {"TERTIARY", "UNIVERSITY"} else "Class",
                "subject_label": "Course Unit" if code in {"TERTIARY", "UNIVERSITY"} else "Subject",
                "period_label": "Semester" if code in {"TERTIARY", "UNIVERSITY"} else "Academic Period",
                "report_label": "Academic Report",
                "candidate_class": False,
                "is_active": True,
            },
        )


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("orgsettings", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AcademicFramework",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=48, unique=True)),
                ("name", models.CharField(max_length=160)),
                ("country_code", models.CharField(blank=True, max_length=2)),
                ("description", models.TextField(blank=True)),
                ("default_terminology", models.JSONField(blank=True, default=dict)),
                ("default_settings", models.JSONField(blank=True, default=dict)),
                ("is_system_template", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("country_code", "name")},
        ),
        migrations.CreateModel(
            name="EducationStage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=32, unique=True)),
                ("name", models.CharField(max_length=96)),
                ("local_name", models.CharField(blank=True, max_length=96)),
                ("description", models.TextField(blank=True)),
                ("order", models.PositiveSmallIntegerField(default=1)),
                ("default_period_type", models.CharField(choices=[("TERM", "Term"), ("SEMESTER", "Semester"), ("YEAR", "Academic Year"), ("CUSTOM", "Custom Period")], default="TERM", max_length=16)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("is_system", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ("order", "name")},
        ),
        migrations.CreateModel(
            name="InstitutionEducationProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("institution_type", models.CharField(choices=[("ECD", "Early Childhood Centre"), ("PRIMARY", "Primary School"), ("SECONDARY", "Secondary School"), ("TERTIARY", "Tertiary or Vocational Institution"), ("UNIVERSITY", "University"), ("MIXED", "Mixed Institution"), ("OTHER", "Other Institution")], default="MIXED", max_length=24)),
                ("country_code", models.CharField(default="UG", max_length=2)),
                ("locale", models.CharField(default="en-UG", max_length=16)),
                ("terminology", models.JSONField(blank=True, default=dict)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("use_local_terminology", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="education_profile", to="orgsettings.organizationprofile")),
                ("primary_framework", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="institution_profiles", to="education_frameworks.academicframework")),
            ],
            options={"ordering": ("organization__name",)},
        ),
        migrations.CreateModel(
            name="FrameworkStage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("local_name", models.CharField(blank=True, max_length=96)),
                ("class_label", models.CharField(default="Class", max_length=48)),
                ("subject_label", models.CharField(default="Subject", max_length=48)),
                ("period_label", models.CharField(default="Term", max_length=48)),
                ("report_label", models.CharField(default="Report Card", max_length=48)),
                ("candidate_class", models.BooleanField(default=False)),
                ("terminology", models.JSONField(blank=True, default=dict)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("framework", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stage_settings", to="education_frameworks.academicframework")),
                ("stage", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="framework_settings", to="education_frameworks.educationstage")),
            ],
            options={"ordering": ("framework", "stage__order")},
        ),
        migrations.CreateModel(
            name="LevelStageMapping",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("legacy_level_id", models.PositiveBigIntegerField()),
                ("legacy_level_name", models.CharField(max_length=128)),
                ("local_name", models.CharField(blank=True, max_length=128)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="level_mappings", to="education_frameworks.institutioneducationprofile")),
                ("stage", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="legacy_level_mappings", to="education_frameworks.educationstage")),
            ],
            options={"ordering": ("legacy_level_name",)},
        ),
        migrations.CreateModel(
            name="CampusEducationStage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("local_name", models.CharField(blank=True, max_length=96)),
                ("academic_period_type", models.CharField(choices=[("TERM", "Term"), ("SEMESTER", "Semester"), ("YEAR", "Academic Year"), ("CUSTOM", "Custom Period")], default="TERM", max_length=16)),
                ("grading_scale_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("grading_scale_name", models.CharField(blank=True, max_length=128)),
                ("report_layout_key", models.CharField(blank=True, max_length=64)),
                ("terminology", models.JSONField(blank=True, default=dict)),
                ("candidate_settings", models.JSONField(blank=True, default=dict)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("campus", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="education_stages", to="orgsettings.campus")),
                ("framework_stage", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="campus_configurations", to="education_frameworks.frameworkstage")),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="campus_stages", to="education_frameworks.institutioneducationprofile")),
                ("stage", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="campus_configurations", to="education_frameworks.educationstage")),
            ],
            options={"ordering": ("campus__name", "stage__order")},
        ),
        migrations.AddConstraint(
            model_name="frameworkstage",
            constraint=models.UniqueConstraint(fields=("framework", "stage"), name="uniq_framework_stage"),
        ),
        migrations.AddConstraint(
            model_name="levelstagemapping",
            constraint=models.UniqueConstraint(fields=("profile", "legacy_level_id"), name="uniq_profile_legacy_level"),
        ),
        migrations.AddConstraint(
            model_name="campuseducationstage",
            constraint=models.UniqueConstraint(fields=("campus", "stage"), name="uniq_campus_education_stage"),
        ),
        migrations.RunPython(seed_framework_templates, migrations.RunPython.noop),
    ]
