from django import forms
from django.utils import timezone

from .models import Author, Book, BookCopy, BookLoan, Category, Fine, Reservation


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class AuthorForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ["name", "bio", "is_active"]
        widgets = {"bio": forms.Textarea(attrs={"rows": 3})}


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ["title", "authors", "category", "isbn", "publisher", "published_year", "edition", "description", "cover_image", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "published_year": forms.NumberInput(attrs={"placeholder": "e.g., 2024", "min": "1800", "max": "2100"}),
        }

    def clean_published_year(self):
        year = self.cleaned_data.get("published_year")
        if year and year > timezone.localdate().year + 1:
            raise forms.ValidationError("Published year cannot be far in the future.")
        return year


class BookCopyForm(forms.ModelForm):
    class Meta:
        model = BookCopy
        fields = ["book", "copy_code", "barcode", "status", "location", "acquisition_date", "price", "notes", "is_active"]
        widgets = {
            "acquisition_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        if self.instance and self.instance.pk and status != BookCopy.CHECKED_OUT:
            open_loan = BookLoan.objects.filter(copy=self.instance, status=BookLoan.OPEN).exists()
            if open_loan:
                self.add_error("status", "This copy has an open loan. Return the loan before changing copy status.")
        return cleaned


class BookLoanForm(forms.ModelForm):
    class Meta:
        model = BookLoan
        fields = ["copy", "borrower_type", "student", "staff", "due_date", "notes"]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned = super().clean()
        copy = cleaned.get("copy")
        borrower_type = cleaned.get("borrower_type")
        student = cleaned.get("student")
        staff = cleaned.get("staff")
        due_date = cleaned.get("due_date")

        if borrower_type == BookLoan.BORROWER_TYPE_STUDENT:
            if not student:
                self.add_error("student", "Student is required for student borrower type.")
            if staff:
                self.add_error("staff", "Do not select staff for a student loan.")
        if borrower_type == BookLoan.BORROWER_TYPE_STAFF:
            if not staff:
                self.add_error("staff", "Staff is required for staff borrower type.")
            if student:
                self.add_error("student", "Do not select student for a staff loan.")
        if due_date and due_date < timezone.localdate():
            self.add_error("due_date", "Due date cannot be in the past.")
        if copy:
            if copy.status != BookCopy.AVAILABLE:
                self.add_error("copy", f"This copy is not available (current status: {copy.get_status_display()}).")
            open_loan = BookLoan.objects.filter(copy=copy, status=BookLoan.OPEN)
            if self.instance and self.instance.pk:
                open_loan = open_loan.exclude(pk=self.instance.pk)
            if open_loan.exists():
                self.add_error("copy", "This copy already has an open loan.")
        return cleaned


class CheckInForm(forms.Form):
    copy_code_or_barcode = forms.CharField(max_length=128, label="Copy Code or Barcode", help_text="Scan or enter the book copy code/barcode")


class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ["book", "borrower_type", "student", "staff", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def clean(self):
        cleaned = super().clean()
        book = cleaned.get("book")
        borrower_type = cleaned.get("borrower_type")
        student = cleaned.get("student")
        staff = cleaned.get("staff")

        if borrower_type == Reservation.BORROWER_TYPE_STUDENT:
            if not student:
                self.add_error("student", "Student is required for student borrower type.")
            if staff:
                self.add_error("staff", "Do not select staff for a student reservation.")
        if borrower_type == Reservation.BORROWER_TYPE_STAFF:
            if not staff:
                self.add_error("staff", "Staff is required for staff borrower type.")
            if student:
                self.add_error("student", "Do not select student for a staff reservation.")
        if book and book.available_copies_count() > 0:
            self.add_error("book", "This book has available copies. Create a loan instead of a reservation.")
        if book and borrower_type == Reservation.BORROWER_TYPE_STUDENT and student:
            existing = Reservation.objects.filter(book=book, borrower_type=borrower_type, student=student, status=Reservation.PENDING)
            if existing.exists():
                self.add_error("student", "This student already has a pending reservation for this book.")
        if book and borrower_type == Reservation.BORROWER_TYPE_STAFF and staff:
            existing = Reservation.objects.filter(book=book, borrower_type=borrower_type, staff=staff, status=Reservation.PENDING)
            if existing.exists():
                self.add_error("staff", "This staff member already has a pending reservation for this book.")
        return cleaned


class FineForm(forms.ModelForm):
    class Meta:
        model = Fine
        fields = ["amount", "reason", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is not None and amount < 0:
            raise forms.ValidationError("Fine amount cannot be negative.")
        return amount
