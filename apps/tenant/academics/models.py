import re
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models


def normalize_academic_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "-", str(value or "").strip().upper()).strip("-")


class GradingScale(models.Model):
    name = models.CharField(max_length=128, unique=True)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-is_default", "name")

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if self.is_default:
            GradingScale.objects.filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)


class GradeRange(models.Model):
    scale = models.ForeignKey(GradingScale, on_delete=models.CASCADE, related_name="ranges")
    grade = models.CharField(max_length=8)
    min_score = models.DecimalField(max_digits=5, decimal_places=2)
    max_score = models.DecimalField(max_digits=5, decimal_places=2)
    grade_point = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    remark = models.CharField(max_length=64, blank=True)
    order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ("scale", "order", "-min_score")
        unique_together = ("scale", "grade")

    def __str__(self) -> str:
        return f"{self.scale.name} - {self.grade} ({self.min_score}-{self.max_score})"

    def clean(self):
        super().clean()
        if self.min_score > self.max_score:
            raise ValidationError("Minimum score cannot be greater than maximum score")

    def contains_score(self, score: Decimal) -> bool:
        return self.min_score <= score <= self.max_score


class AcademicYear(models.Model):
    name = models.CharField(max_length=32, unique=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ("-name",)

    def __str__(self) -> str:
        return self.name


class AcademicTerm(models.Model):
    TERM = "TERM"
    SEMESTER = "SEMESTER"

    TYPE_CHOICES = (
        (TERM, "Term"),
        (SEMESTER, "Semester"),
    )

    year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    name = models.CharField(max_length=32)
    type = models.CharField(max_length=16, choices=TYPE_CHOICES, default=TERM)
    order = models.PositiveSmallIntegerField(default=1)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ("-year__name", "order")
        unique_together = ("year", "name")

    def __str__(self) -> str:
        return f"{self.year} - {self.name}"


class Level(models.Model):
    name = models.CharField(max_length=64, unique=True)
    order = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("order", "name")

    def __str__(self) -> str:
        return self.name


class Program(models.Model):
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        unique_together = ("name", "code")

    def __str__(self) -> str:
        return self.name


class ClassGroup(models.Model):
    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32, blank=True)
    level = models.ForeignKey(Level, on_delete=models.SET_NULL, null=True, blank=True)
    program = models.ForeignKey(Program, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Stream(models.Model):
    class_group = models.ForeignKey(ClassGroup, on_delete=models.CASCADE, related_name="streams")
    name = models.CharField(max_length=32)
    capacity = models.PositiveSmallIntegerField(default=40)
    class_teacher = models.ForeignKey(
        "teachers.TeacherProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_streams",
    )
    room = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("class_group", "name")
        unique_together = ("class_group", "name")

    def __str__(self) -> str:
        return f"{self.class_group} - {self.name}"

    def get_student_count(self) -> int:
        from apps.tenant.students.models import StudentProfile

        return StudentProfile.objects.filter(stream=self, is_active=True).count()

    def is_full(self) -> bool:
        return self.get_student_count() >= self.capacity


class Course(models.Model):
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32, blank=True)
    level = models.ForeignKey(Level, on_delete=models.SET_NULL, null=True, blank=True)
    program = models.ForeignKey(Program, on_delete=models.SET_NULL, null=True, blank=True)
    credits = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        if self.code:
            return f"{self.code} - {self.name}"
        return self.name


class ProgrammePathway(models.Model):
    code = models.CharField(max_length=48, unique=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    program = models.ForeignKey(
        Program,
        on_delete=models.PROTECT,
        related_name="programme_pathways",
    )
    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="programme_pathways",
    )
    stage = models.ForeignKey(
        "education_frameworks.EducationStage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="programme_pathways",
    )
    priority = models.IntegerField(default=0)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-priority", "-is_default", "name")

    def __str__(self) -> str:
        return self.name

    def clean(self):
        super().clean()
        self.code = normalize_academic_code(self.code)
        errors = {}
        if self.program_id and not self.program.is_active:
            errors["program"] = "Choose an active programme."
        if self.is_active:
            duplicate = type(self).objects.filter(
                program_id=self.program_id,
                campus_id=self.campus_id,
                stage_id=self.stage_id,
                priority=self.priority,
                is_active=True,
            )
            if self.pk:
                duplicate = duplicate.exclude(pk=self.pk)
            if duplicate.exists():
                errors["__all__"] = "Another active pathway has the same programme, scope and priority."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.code = normalize_academic_code(self.code)
        super().save(*args, **kwargs)

    @property
    def scope_label(self) -> str:
        parts = [str(self.program)]
        if self.campus_id:
            parts.append(str(self.campus))
        if self.stage_id:
            parts.append(str(self.stage))
        return " · ".join(parts)


class ProgrammePathwayLevel(models.Model):
    pathway = models.ForeignKey(
        ProgrammePathway,
        on_delete=models.CASCADE,
        related_name="pathway_levels",
    )
    level = models.ForeignKey(
        Level,
        on_delete=models.PROTECT,
        related_name="programme_pathway_levels",
    )
    sequence = models.PositiveSmallIntegerField(default=1)
    minimum_terms = models.PositiveSmallIntegerField(default=1)
    is_entry = models.BooleanField(default=False)
    is_exit = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("pathway", "sequence", "level__order", "level__name")
        constraints = [
            models.UniqueConstraint(
                fields=("pathway", "level"),
                name="uniq_pathway_level",
            ),
            models.UniqueConstraint(
                fields=("pathway", "sequence"),
                name="uniq_pathway_level_sequence",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.pathway} — {self.level}"

    def clean(self):
        super().clean()
        errors = {}
        if self.level_id and not self.level.is_active:
            errors["level"] = "Choose an active level."
        if self.minimum_terms < 1:
            errors["minimum_terms"] = "Minimum terms must be at least one."
        if self.is_active and self.pathway_id:
            if self.is_entry:
                duplicate = type(self).objects.filter(pathway=self.pathway, is_entry=True, is_active=True)
                if self.pk:
                    duplicate = duplicate.exclude(pk=self.pk)
                if duplicate.exists():
                    errors["is_entry"] = "This pathway already has an active entry level."
            if self.is_exit:
                duplicate = type(self).objects.filter(pathway=self.pathway, is_exit=True, is_active=True)
                if self.pk:
                    duplicate = duplicate.exclude(pk=self.pk)
                if duplicate.exists():
                    errors["is_exit"] = "This pathway already has an active exit level."
        if errors:
            raise ValidationError(errors)


class SubjectCombination(models.Model):
    code = models.CharField(max_length=48, unique=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    pathway = models.ForeignKey(
        ProgrammePathway,
        on_delete=models.CASCADE,
        related_name="subject_combinations",
    )
    level = models.ForeignKey(
        Level,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subject_combinations",
    )
    minimum_subjects = models.PositiveSmallIntegerField(default=1)
    maximum_subjects = models.PositiveSmallIntegerField(null=True, blank=True)
    priority = models.IntegerField(default=0)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("pathway", "-priority", "-is_default", "name")

    def __str__(self) -> str:
        return self.name

    def clean(self):
        super().clean()
        self.code = normalize_academic_code(self.code)
        errors = {}
        if self.maximum_subjects is not None and self.maximum_subjects < self.minimum_subjects:
            errors["maximum_subjects"] = "Maximum subjects cannot be below minimum subjects."
        if self.level_id and self.pathway_id:
            if not self.pathway.pathway_levels.filter(level_id=self.level_id, is_active=True).exists():
                errors["level"] = "Choose a level that belongs to this pathway."
        if self.is_active:
            duplicate = type(self).objects.filter(
                pathway_id=self.pathway_id,
                level_id=self.level_id,
                priority=self.priority,
                is_active=True,
            )
            if self.pk:
                duplicate = duplicate.exclude(pk=self.pk)
            if duplicate.exists():
                errors["__all__"] = "Another active combination has the same pathway, level and priority."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.code = normalize_academic_code(self.code)
        super().save(*args, **kwargs)


class SubjectCombinationCourse(models.Model):
    CORE = "CORE"
    ELECTIVE = "ELECTIVE"
    OPTIONAL = "OPTIONAL"

    ROLE_CHOICES = (
        (CORE, "Core subject"),
        (ELECTIVE, "Elective subject"),
        (OPTIONAL, "Optional subject"),
    )

    combination = models.ForeignKey(
        SubjectCombination,
        on_delete=models.CASCADE,
        related_name="course_memberships",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name="subject_combination_memberships",
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=CORE)
    subject_group = models.CharField(max_length=48, blank=True)
    order = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    settings = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("combination", "order", "course__name")
        constraints = [
            models.UniqueConstraint(
                fields=("combination", "course"),
                name="uniq_combination_course",
            )
        ]

    def __str__(self) -> str:
        return f"{self.combination} — {self.course}"

    def clean(self):
        super().clean()
        errors = {}
        if self.course_id and not self.course.is_active:
            errors["course"] = "Choose an active course."
        if self.course_id and self.combination_id:
            pathway_program_id = self.combination.pathway.program_id
            if self.course.program_id and self.course.program_id != pathway_program_id:
                errors["course"] = "The course belongs to a different programme."
        if errors:
            raise ValidationError(errors)


class ClassGroupPathwayAssignment(models.Model):
    class_group = models.ForeignKey(
        ClassGroup,
        on_delete=models.CASCADE,
        related_name="pathway_assignments",
    )
    pathway = models.ForeignKey(
        ProgrammePathway,
        on_delete=models.PROTECT,
        related_name="class_group_assignments",
    )
    subject_combination = models.ForeignKey(
        SubjectCombination,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="class_group_assignments",
    )
    academic_term = models.ForeignKey(
        AcademicTerm,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="class_group_pathway_assignments",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("class_group", "-academic_term__year__name", "-academic_term__order", "-pk")
        constraints = [
            models.UniqueConstraint(
                fields=("class_group", "pathway", "academic_term"),
                name="uniq_class_pathway_term",
            )
        ]

    def __str__(self) -> str:
        return f"{self.class_group} — {self.pathway}"

    def clean(self):
        super().clean()
        errors = {}
        if self.class_group_id and self.pathway_id:
            if self.class_group.program_id and self.class_group.program_id != self.pathway.program_id:
                errors["pathway"] = "The pathway belongs to a different programme."
            if self.pathway.campus_id and self.class_group.campus_id != self.pathway.campus_id:
                errors["pathway"] = "The pathway belongs to a different campus."
            active_levels = self.pathway.pathway_levels.filter(is_active=True)
            if self.class_group.level_id and active_levels.exists():
                if not active_levels.filter(level_id=self.class_group.level_id).exists():
                    errors["pathway"] = "The class-group level is not part of this pathway."
        if self.subject_combination_id and self.pathway_id:
            if self.subject_combination.pathway_id != self.pathway_id:
                errors["subject_combination"] = "The combination must belong to the selected pathway."
            if self.class_group_id and self.subject_combination.level_id:
                if self.class_group.level_id != self.subject_combination.level_id:
                    errors["subject_combination"] = "The combination is configured for a different level."
        if errors:
            raise ValidationError(errors)


class CourseOffering(models.Model):
    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    term = models.ForeignKey(AcademicTerm, on_delete=models.CASCADE)
    class_group = models.ForeignKey(ClassGroup, on_delete=models.SET_NULL, null=True, blank=True)
    teacher = models.ForeignKey(
        "teachers.TeacherProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-term__year__name", "term__order", "course__name")

    def __str__(self) -> str:
        return f"{self.term} - {self.course}"

    def clean(self):
        super().clean()

        if self.campus and self.class_group and self.class_group.campus:
            if self.campus != self.class_group.campus:
                raise ValidationError({
                    "campus": f"Offering campus must match class group campus ({self.class_group.campus})"
                })

        if self.campus and self.teacher and self.teacher.campus:
            if self.campus != self.teacher.campus:
                raise ValidationError({
                    "campus": f"Offering campus must match teacher campus ({self.teacher.campus})"
                })

        if not self.campus and self.class_group and self.class_group.campus:
            self.campus = self.class_group.campus

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Enrollment(models.Model):
    ACTIVE = "ACTIVE"
    DROPPED = "DROPPED"

    STATUS_CHOICES = (
        (ACTIVE, "Active"),
        (DROPPED, "Dropped"),
    )

    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    offering = models.ForeignKey(CourseOffering, on_delete=models.CASCADE)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("offering", "student")
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.student} -> {self.offering}"

    def clean(self):
        super().clean()

        if self.campus and self.offering and self.offering.campus:
            if self.campus != self.offering.campus:
                raise ValidationError({
                    "campus": f"Enrollment campus must match offering campus ({self.offering.campus})"
                })

        if self.campus and self.student and self.student.campus:
            if self.campus != self.student.campus:
                raise ValidationError({
                    "campus": f"Enrollment campus must match student campus ({self.student.campus})"
                })

        if not self.campus:
            if self.offering and self.offering.campus:
                self.campus = self.offering.campus
            elif self.student and self.student.campus:
                self.campus = self.student.campus

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
