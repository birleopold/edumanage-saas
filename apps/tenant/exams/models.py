from django.db import models


class Exam(models.Model):
    name = models.CharField(max_length=128)
    term = models.ForeignKey("academics.AcademicTerm", on_delete=models.CASCADE)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-term__year__name", "term__order", "name")
        unique_together = ("term", "name")

    def __str__(self) -> str:
        return f"{self.term} - {self.name}"


class ExamPaper(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="papers")
    offering = models.ForeignKey("academics.CourseOffering", on_delete=models.CASCADE)
    max_score = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    weight = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    is_published = models.BooleanField(default=False)
    date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        unique_together = ("exam", "offering")

    def __str__(self) -> str:
        return f"{self.exam} - {self.offering}"


class ExamScore(models.Model):
    paper = models.ForeignKey(ExamPaper, on_delete=models.CASCADE, related_name="scores")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    graded_by = models.ForeignKey(
        "teachers.TeacherProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    graded_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("student__last_name", "student__first_name")
        unique_together = ("paper", "student")

    def __str__(self) -> str:
        return f"{self.student} -> {self.paper}"
