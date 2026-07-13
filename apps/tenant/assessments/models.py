from django.db import models


class Assessment(models.Model):
    offering = models.ForeignKey("academics.CourseOffering", on_delete=models.CASCADE)
    name = models.CharField(max_length=128)
    max_score = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    weight = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    date = models.DateField(null=True, blank=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        unique_together = ("offering", "name")

    def __str__(self) -> str:
        return f"{self.offering} - {self.name}"


class AssessmentScore(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="scores")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    report_comment = models.TextField(blank=True)
    report_comment_ai_assisted = models.BooleanField(default=False)
    graded_by = models.ForeignKey(
        "teachers.TeacherProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    graded_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("student__last_name", "student__first_name")
        unique_together = ("assessment", "student")

    def __str__(self) -> str:
        return f"{self.student} -> {self.assessment}"
