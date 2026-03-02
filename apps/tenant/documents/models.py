from django.conf import settings
from django.db import connection, models


def document_upload_to(instance, filename: str) -> str:
    schema = getattr(connection, "schema_name", "public") or "public"
    return f"{schema}/documents/{filename}"


class Document(models.Model):
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
    description = models.TextField(blank=True)
    file = models.FileField(upload_to=document_upload_to)
    audience = models.CharField(max_length=16, choices=AUDIENCE_CHOICES, default=ALL)
    is_active = models.BooleanField(default=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.title
