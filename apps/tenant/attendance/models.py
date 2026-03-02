from django.db import models


class AttendanceSession(models.Model):
    offering = models.ForeignKey("academics.CourseOffering", on_delete=models.CASCADE)
    date = models.DateField()
    taken_by = models.ForeignKey(
        "teachers.TeacherProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("offering", "date")
        ordering = ("-date", "-created_at")

    def __str__(self) -> str:
        return f"{self.offering} @ {self.date}"


class AttendanceEntry(models.Model):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    LATE = "LATE"
    EXCUSED = "EXCUSED"

    STATUS_CHOICES = (
        (PRESENT, "Present"),
        (ABSENT, "Absent"),
        (LATE, "Late"),
        (EXCUSED, "Excused"),
    )

    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name="entries")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PRESENT)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ("session", "student")
        ordering = ("student__last_name", "student__first_name")

    def __str__(self) -> str:
        return f"{self.student} -> {self.session} ({self.status})"
