import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0003_gradingscale_stream_graderange"),
        ("education_frameworks", "0001_initial"),
        ("orgsettings", "0006_merge_20260624_1447"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProgrammePathway",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=48, unique=True)),
                ("name", models.CharField(max_length=128)),
                ("description", models.TextField(blank=True)),
                ("priority", models.IntegerField(default=0)),
                ("is_default", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "campus",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="programme_pathways",
                        to="orgsettings.campus",
                    ),
                ),
                (
                    "program",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="programme_pathways",
                        to="academics.program",
                    ),
                ),
                (
                    "stage",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="programme_pathways",
                        to="education_frameworks.educationstage",
                    ),
                ),
            ],
            options={"ordering": ("-priority", "-is_default", "name")},
        ),
        migrations.CreateModel(
            name="ProgrammePathwayLevel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence", models.PositiveSmallIntegerField(default=1)),
                ("minimum_terms", models.PositiveSmallIntegerField(default=1)),
                ("is_entry", models.BooleanField(default=False)),
                ("is_exit", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "level",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="programme_pathway_levels",
                        to="academics.level",
                    ),
                ),
                (
                    "pathway",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pathway_levels",
                        to="academics.programmepathway",
                    ),
                ),
            ],
            options={"ordering": ("pathway", "sequence", "level__order", "level__name")},
        ),
        migrations.CreateModel(
            name="SubjectCombination",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=48, unique=True)),
                ("name", models.CharField(max_length=128)),
                ("description", models.TextField(blank=True)),
                ("minimum_subjects", models.PositiveSmallIntegerField(default=1)),
                ("maximum_subjects", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("priority", models.IntegerField(default=0)),
                ("is_default", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "level",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="subject_combinations",
                        to="academics.level",
                    ),
                ),
                (
                    "pathway",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subject_combinations",
                        to="academics.programmepathway",
                    ),
                ),
            ],
            options={"ordering": ("pathway", "-priority", "-is_default", "name")},
        ),
        migrations.CreateModel(
            name="SubjectCombinationCourse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("CORE", "Core subject"),
                            ("ELECTIVE", "Elective subject"),
                            ("OPTIONAL", "Optional subject"),
                        ],
                        default="CORE",
                        max_length=16,
                    ),
                ),
                ("subject_group", models.CharField(blank=True, max_length=48)),
                ("order", models.PositiveSmallIntegerField(default=1)),
                ("is_active", models.BooleanField(default=True)),
                ("settings", models.JSONField(blank=True, default=dict)),
                (
                    "combination",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="course_memberships",
                        to="academics.subjectcombination",
                    ),
                ),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subject_combination_memberships",
                        to="academics.course",
                    ),
                ),
            ],
            options={"ordering": ("combination", "order", "course__name")},
        ),
        migrations.CreateModel(
            name="ClassGroupPathwayAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "academic_term",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="class_group_pathway_assignments",
                        to="academics.academicterm",
                    ),
                ),
                (
                    "class_group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pathway_assignments",
                        to="academics.classgroup",
                    ),
                ),
                (
                    "pathway",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="class_group_assignments",
                        to="academics.programmepathway",
                    ),
                ),
                (
                    "subject_combination",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="class_group_assignments",
                        to="academics.subjectcombination",
                    ),
                ),
            ],
            options={"ordering": ("class_group", "-academic_term__year__name", "-academic_term__order", "-pk")},
        ),
        migrations.AddConstraint(
            model_name="programmepathwaylevel",
            constraint=models.UniqueConstraint(fields=("pathway", "level"), name="uniq_pathway_level"),
        ),
        migrations.AddConstraint(
            model_name="programmepathwaylevel",
            constraint=models.UniqueConstraint(fields=("pathway", "sequence"), name="uniq_pathway_level_sequence"),
        ),
        migrations.AddConstraint(
            model_name="subjectcombinationcourse",
            constraint=models.UniqueConstraint(fields=("combination", "course"), name="uniq_combination_course"),
        ),
        migrations.AddConstraint(
            model_name="classgrouppathwayassignment",
            constraint=models.UniqueConstraint(
                fields=("class_group", "pathway", "academic_term"),
                name="uniq_class_pathway_term",
            ),
        ),
    ]
