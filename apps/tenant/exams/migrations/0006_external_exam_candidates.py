from decimal import Decimal

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0004_programme_pathways_subject_combinations"),
        ("education_frameworks", "0001_initial"),
        ("exams", "0005_assessment_framework_links"),
        ("orgsettings", "0006_merge_20260624_1447"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ExternalExamBoard",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=32, unique=True)),
                ("name", models.CharField(max_length=128)),
                (
                    "board_type",
                    models.CharField(
                        choices=[
                            ("NATIONAL", "National examination board"),
                            ("REGIONAL", "Regional examination board"),
                            ("INTERNATIONAL", "International examination board"),
                            ("PROFESSIONAL", "Professional examination body"),
                            ("OTHER", "Other external body"),
                        ],
                        default="NATIONAL",
                        max_length=24,
                    ),
                ),
                ("country_code", models.CharField(blank=True, max_length=2)),
                ("website", models.URLField(blank=True)),
                ("contact_email", models.EmailField(blank=True, max_length=254)),
                ("candidate_number_label", models.CharField(default="Candidate number", max_length=64)),
                ("subject_code_label", models.CharField(default="Subject code", max_length=64)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="ExternalExamCentre",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=48)),
                ("name", models.CharField(max_length=128)),
                ("address", models.TextField(blank=True)),
                ("contact_name", models.CharField(blank=True, max_length=128)),
                ("contact_phone", models.CharField(blank=True, max_length=48)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "board",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="centres",
                        to="exams.externalexamboard",
                    ),
                ),
                (
                    "campus",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="external_exam_centres",
                        to="orgsettings.campus",
                    ),
                ),
            ],
            options={"ordering": ("board__name", "code")},
        ),
        migrations.CreateModel(
            name="ExternalExamSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=48)),
                ("name", models.CharField(max_length=128)),
                ("registration_opens", models.DateField(blank=True, null=True)),
                ("registration_closes", models.DateField(blank=True, null=True)),
                ("exam_starts", models.DateField(blank=True, null=True)),
                ("exam_ends", models.DateField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DRAFT", "Draft"),
                            ("REGISTRATION_OPEN", "Registration open"),
                            ("REGISTRATION_CLOSED", "Registration closed"),
                            ("RESULTS_PENDING", "Results pending"),
                            ("RESULTS_RELEASED", "Results released"),
                            ("ARCHIVED", "Archived"),
                        ],
                        default="DRAFT",
                        max_length=24,
                    ),
                ),
                ("candidate_prefix", models.CharField(blank=True, max_length=32)),
                ("candidate_number_padding", models.PositiveSmallIntegerField(default=4)),
                ("next_candidate_sequence", models.PositiveIntegerField(default=1)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "academic_year",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="external_exam_sessions",
                        to="academics.academicyear",
                    ),
                ),
                (
                    "board",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sessions",
                        to="exams.externalexamboard",
                    ),
                ),
                (
                    "campus",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="external_exam_sessions",
                        to="orgsettings.campus",
                    ),
                ),
                (
                    "centre",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sessions",
                        to="exams.externalexamcentre",
                    ),
                ),
                (
                    "level",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="external_exam_sessions",
                        to="academics.level",
                    ),
                ),
                (
                    "linked_exam",
                    models.ForeignKey(
                        blank=True,
                        help_text="Optional compatibility link. Internal exam papers and scores remain authoritative.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="external_sessions",
                        to="exams.exam",
                    ),
                ),
                (
                    "program",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="external_exam_sessions",
                        to="academics.program",
                    ),
                ),
                (
                    "stage",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="external_exam_sessions",
                        to="education_frameworks.educationstage",
                    ),
                ),
            ],
            options={"ordering": ("-academic_year__name", "board__name", "name")},
        ),
        migrations.CreateModel(
            name="ExternalExamSubject",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("subject_code", models.CharField(max_length=48)),
                ("display_name", models.CharField(blank=True, max_length=128)),
                (
                    "max_score",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=7,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.01"))],
                    ),
                ),
                ("is_compulsory", models.BooleanField(default=False)),
                ("order", models.PositiveSmallIntegerField(default=1)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="external_exam_subjects",
                        to="academics.course",
                    ),
                ),
                (
                    "linked_paper",
                    models.ForeignKey(
                        blank=True,
                        help_text="Optional compatibility link. Existing exam scores are not copied.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="external_subjects",
                        to="exams.exampaper",
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subjects",
                        to="exams.externalexamsession",
                    ),
                ),
            ],
            options={"ordering": ("session", "order", "course__name")},
        ),
        migrations.CreateModel(
            name="ExternalCandidate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("candidate_number", models.CharField(max_length=64)),
                ("board_reference", models.CharField(blank=True, max_length=128)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DRAFT", "Draft"),
                            ("REGISTERED", "Registered"),
                            ("SUBMITTED", "Submitted to board"),
                            ("APPROVED", "Approved by board"),
                            ("WITHDRAWN", "Withdrawn"),
                        ],
                        default="REGISTERED",
                        max_length=16,
                    ),
                ),
                ("registration_date", models.DateField(default=django.utils.timezone.localdate)),
                ("accommodations", models.JSONField(blank=True, default=dict)),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "centre",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="candidates",
                        to="exams.externalexamcentre",
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="candidates",
                        to="exams.externalexamsession",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="external_exam_candidates",
                        to="students.studentprofile",
                    ),
                ),
            ],
            options={"ordering": ("session", "candidate_number")},
        ),
        migrations.CreateModel(
            name="ExternalCandidateSubject",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("REGISTERED", "Registered"),
                            ("WITHDRAWN", "Withdrawn"),
                            ("ABSENT", "Absent"),
                            ("EXEMPT", "Exempt"),
                        ],
                        default="REGISTERED",
                        max_length=16,
                    ),
                ),
                ("paper_reference", models.CharField(blank=True, max_length=64)),
                ("registered_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "candidate",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subject_registrations",
                        to="exams.externalcandidate",
                    ),
                ),
                (
                    "subject",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="candidate_registrations",
                        to="exams.externalexamsubject",
                    ),
                ),
            ],
            options={"ordering": ("candidate", "subject__order", "subject__course__name")},
        ),
        migrations.CreateModel(
            name="ExternalExamResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("score", models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True)),
                (
                    "percentage",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=5,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0")),
                            django.core.validators.MaxValueValidator(Decimal("100")),
                        ],
                    ),
                ),
                ("grade", models.CharField(blank=True, max_length=16)),
                (
                    "result_status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("PASS", "Pass"),
                            ("FAIL", "Fail"),
                            ("ABSENT", "Absent"),
                            ("WITHHELD", "Withheld"),
                            ("EXEMPT", "Exempt"),
                        ],
                        default="PENDING",
                        max_length=16,
                    ),
                ),
                ("source_reference", models.CharField(blank=True, max_length=128)),
                ("is_official", models.BooleanField(default=True)),
                ("released_at", models.DateTimeField(blank=True, null=True)),
                ("raw_data", models.JSONField(blank=True, default=dict)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "candidate_subject",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="official_result",
                        to="exams.externalcandidatesubject",
                    ),
                ),
                (
                    "imported_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="external_exam_results_imported",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "linked_exam_score",
                    models.OneToOneField(
                        blank=True,
                        help_text="Optional compatibility link. The internal exam score remains unchanged.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="external_result",
                        to="exams.examscore",
                    ),
                ),
            ],
            options={"ordering": ("candidate_subject__candidate__candidate_number", "candidate_subject__subject__order")},
        ),
        migrations.CreateModel(
            name="ExternalResultImportBatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file_name", models.CharField(max_length=255)),
                ("dry_run", models.BooleanField(default=True)),
                ("row_count", models.PositiveIntegerField(default=0)),
                ("accepted_count", models.PositiveIntegerField(default=0)),
                ("rejected_count", models.PositiveIntegerField(default=0)),
                ("errors", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "imported_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="external_result_import_batches",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="result_import_batches",
                        to="exams.externalexamsession",
                    ),
                ),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddConstraint(
            model_name="externalexamcentre",
            constraint=models.UniqueConstraint(fields=("board", "code"), name="uniq_ext_board_centre_code"),
        ),
        migrations.AddConstraint(
            model_name="externalexamsession",
            constraint=models.UniqueConstraint(fields=("board", "code"), name="uniq_ext_board_session_code"),
        ),
        migrations.AddConstraint(
            model_name="externalexamsubject",
            constraint=models.UniqueConstraint(fields=("session", "course"), name="uniq_ext_session_course"),
        ),
        migrations.AddConstraint(
            model_name="externalexamsubject",
            constraint=models.UniqueConstraint(fields=("session", "subject_code"), name="uniq_ext_session_subject_code"),
        ),
        migrations.AddConstraint(
            model_name="externalcandidate",
            constraint=models.UniqueConstraint(fields=("session", "student"), name="uniq_ext_session_student"),
        ),
        migrations.AddConstraint(
            model_name="externalcandidate",
            constraint=models.UniqueConstraint(fields=("session", "candidate_number"), name="uniq_ext_session_candidate_no"),
        ),
        migrations.AddConstraint(
            model_name="externalcandidatesubject",
            constraint=models.UniqueConstraint(fields=("candidate", "subject"), name="uniq_ext_candidate_subject"),
        ),
    ]
