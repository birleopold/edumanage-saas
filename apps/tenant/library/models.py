from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=128, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "Categories"

    def __str__(self) -> str:
        return self.name


class Author(models.Model):
    name = models.CharField(max_length=128)
    bio = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=200)
    authors = models.ManyToManyField(Author, blank=True, related_name="books")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="books")
    isbn = models.CharField(max_length=32, blank=True, unique=True)
    publisher = models.CharField(max_length=200, blank=True)
    published_year = models.PositiveSmallIntegerField(null=True, blank=True)
    edition = models.CharField(max_length=64, blank=True)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to="library/covers/", null=True, blank=True)
    total_copies = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("title",)

    def __str__(self) -> str:
        return self.title

    def available_copies_count(self):
        return self.copies.filter(status=BookCopy.AVAILABLE, is_active=True).count()

    def total_active_copies_count(self):
        return self.copies.filter(is_active=True).count()


class BookCopy(models.Model):
    AVAILABLE = "AVAILABLE"
    CHECKED_OUT = "CHECKED_OUT"
    RESERVED = "RESERVED"
    LOST = "LOST"
    DAMAGED = "DAMAGED"
    MAINTENANCE = "MAINTENANCE"

    STATUS_CHOICES = (
        (AVAILABLE, "Available"),
        (CHECKED_OUT, "Checked Out"),
        (RESERVED, "Reserved"),
        (LOST, "Lost"),
        (DAMAGED, "Damaged"),
        (MAINTENANCE, "Under Maintenance"),
    )

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="copies")
    copy_code = models.CharField(max_length=64, unique=True)
    barcode = models.CharField(max_length=128, unique=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=AVAILABLE)
    location = models.CharField(max_length=128, blank=True, help_text="Shelf/Section location")
    acquisition_date = models.DateField(null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("book__title", "copy_code")
        verbose_name_plural = "Book Copies"

    def __str__(self) -> str:
        return f"{self.book} [{self.copy_code}]"

    def is_available(self):
        return self.status == self.AVAILABLE and self.is_active


class BookLoan(models.Model):
    OPEN = "OPEN"
    RETURNED = "RETURNED"
    OVERDUE = "OVERDUE"

    STATUS_CHOICES = (
        (OPEN, "Open"),
        (RETURNED, "Returned"),
        (OVERDUE, "Overdue"),
    )

    BORROWER_TYPE_STUDENT = "STUDENT"
    BORROWER_TYPE_STAFF = "STAFF"

    BORROWER_TYPE_CHOICES = (
        (BORROWER_TYPE_STUDENT, "Student"),
        (BORROWER_TYPE_STAFF, "Staff"),
    )

    copy = models.ForeignKey(BookCopy, on_delete=models.CASCADE, related_name="loans")
    borrower_type = models.CharField(max_length=16, choices=BORROWER_TYPE_CHOICES, default=BORROWER_TYPE_STUDENT)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, null=True, blank=True, related_name="book_loans")
    staff = models.ForeignKey("hr.StaffProfile", on_delete=models.CASCADE, null=True, blank=True, related_name="book_loans")
    borrowed_at = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    returned_at = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=OPEN)
    checked_out_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="checkouts_processed")
    checked_in_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="checkins_processed")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        borrower = self.student if self.borrower_type == self.BORROWER_TYPE_STUDENT else self.staff
        return f"{self.copy} -> {borrower}"

    def is_overdue(self):
        if self.status == self.RETURNED:
            return False
        return timezone.now().date() > self.due_date

    def days_overdue(self):
        if not self.is_overdue():
            return 0
        return (timezone.now().date() - self.due_date).days

    def calculate_fine(self, fine_per_day=Decimal("10.00")):
        if not self.is_overdue():
            return Decimal("0.00")
        return Decimal(str(self.days_overdue())) * fine_per_day


class Reservation(models.Model):
    PENDING = "PENDING"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"

    STATUS_CHOICES = (
        (PENDING, "Pending"),
        (FULFILLED, "Fulfilled"),
        (CANCELLED, "Cancelled"),
        (EXPIRED, "Expired"),
    )

    BORROWER_TYPE_STUDENT = "STUDENT"
    BORROWER_TYPE_STAFF = "STAFF"

    BORROWER_TYPE_CHOICES = (
        (BORROWER_TYPE_STUDENT, "Student"),
        (BORROWER_TYPE_STAFF, "Staff"),
    )

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="reservations")
    borrower_type = models.CharField(max_length=16, choices=BORROWER_TYPE_CHOICES, default=BORROWER_TYPE_STUDENT)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, null=True, blank=True, related_name="book_reservations")
    staff = models.ForeignKey("hr.StaffProfile", on_delete=models.CASCADE, null=True, blank=True, related_name="book_reservations")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PENDING)
    reserved_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("reserved_at",)

    def __str__(self) -> str:
        borrower = self.student if self.borrower_type == self.BORROWER_TYPE_STUDENT else self.staff
        return f"{self.book} reserved by {borrower}"


class Fine(models.Model):
    UNPAID = "UNPAID"
    PAID = "PAID"
    WAIVED = "WAIVED"

    STATUS_CHOICES = (
        (UNPAID, "Unpaid"),
        (PAID, "Paid"),
        (WAIVED, "Waived"),
    )

    BORROWER_TYPE_STUDENT = "STUDENT"
    BORROWER_TYPE_STAFF = "STAFF"

    BORROWER_TYPE_CHOICES = (
        (BORROWER_TYPE_STUDENT, "Student"),
        (BORROWER_TYPE_STAFF, "Staff"),
    )

    loan = models.ForeignKey(BookLoan, on_delete=models.CASCADE, related_name="fines")
    borrower_type = models.CharField(max_length=16, choices=BORROWER_TYPE_CHOICES, default=BORROWER_TYPE_STUDENT)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, null=True, blank=True, related_name="library_fines")
    staff = models.ForeignKey("hr.StaffProfile", on_delete=models.CASCADE, null=True, blank=True, related_name="library_fines")
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    reason = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=UNPAID)
    issued_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    waived_at = models.DateTimeField(null=True, blank=True)
    waived_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="waived_fines")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-issued_at",)

    def __str__(self) -> str:
        borrower = self.student if self.borrower_type == self.BORROWER_TYPE_STUDENT else self.staff
        return f"Fine for {borrower}: {self.amount}"
