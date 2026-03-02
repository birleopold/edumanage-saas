from django.db import models


class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=128, blank=True)
    isbn = models.CharField(max_length=32, blank=True)
    published_year = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("title",)

    def __str__(self) -> str:
        return self.title


class BookCopy(models.Model):
    AVAILABLE = "AVAILABLE"
    LOST = "LOST"
    DAMAGED = "DAMAGED"

    STATUS_CHOICES = (
        (AVAILABLE, "Available"),
        (LOST, "Lost"),
        (DAMAGED, "Damaged"),
    )

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="copies")
    copy_code = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=AVAILABLE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("book__title", "copy_code")
        unique_together = ("book", "copy_code")

    def __str__(self) -> str:
        return f"{self.book} [{self.copy_code}]"


class BookLoan(models.Model):
    OPEN = "OPEN"
    RETURNED = "RETURNED"

    STATUS_CHOICES = (
        (OPEN, "Open"),
        (RETURNED, "Returned"),
    )

    copy = models.ForeignKey(BookCopy, on_delete=models.CASCADE)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    borrowed_at = models.DateField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True)
    returned_at = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=OPEN)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.copy} -> {self.student}"
