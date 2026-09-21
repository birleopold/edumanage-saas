from django.db import models


class Announcement(models.Model):
    ALL = "ALL"
    TEACHERS = "TEACHERS"
    STUDENTS = "STUDENTS"
    PARENTS = "PARENTS"

    AUDIENCE_CHOICES = (
        (ALL, "All"),
        (TEACHERS, "Teachers"),
        (STUDENTS, "Students"),
        (PARENTS, "Parents"),
    )

    title = models.CharField(max_length=200)
    body = models.TextField()
    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="announcements",
        help_text="Leave blank to publish to every campus.",
    )
    audience = models.CharField(max_length=16, choices=AUDIENCE_CHOICES, default=ALL)
    is_active = models.BooleanField(default=True)
    is_urgent = models.BooleanField(
        default=False,
        help_text="Urgent announcements can be broadcast through SMS/WhatsApp in Phase 2.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["is_active", "audience", "campus"])]

    def __str__(self) -> str:
        return self.title
