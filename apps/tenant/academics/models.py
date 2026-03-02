from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models


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
        
        # Validate campus consistency with class_group
        if self.campus and self.class_group and self.class_group.campus:
            if self.campus != self.class_group.campus:
                raise ValidationError({
                    'campus': f'Offering campus must match class group campus ({self.class_group.campus})'
                })
        
        # Validate campus consistency with teacher
        if self.campus and self.teacher and self.teacher.campus:
            if self.campus != self.teacher.campus:
                raise ValidationError({
                    'campus': f'Offering campus must match teacher campus ({self.teacher.campus})'
                })
        
        # Auto-derive campus from class_group if not set
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
        
        # Validate campus consistency
        if self.campus and self.offering and self.offering.campus:
            if self.campus != self.offering.campus:
                raise ValidationError({
                    'campus': f'Enrollment campus must match offering campus ({self.offering.campus})'
                })
        
        if self.campus and self.student and self.student.campus:
            if self.campus != self.student.campus:
                raise ValidationError({
                    'campus': f'Enrollment campus must match student campus ({self.student.campus})'
                })
        
        # If enrollment campus is not set, derive it from offering or student
        if not self.campus:
            if self.offering and self.offering.campus:
                self.campus = self.offering.campus
            elif self.student and self.student.campus:
                self.campus = self.student.campus

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
