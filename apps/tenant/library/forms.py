from django import forms

from .models import Author, Book, BookCopy, BookLoan, Category, Fine, Reservation


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class AuthorForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ["name", "bio", "is_active"]
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 3}),
        }


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ["title", "authors", "category", "isbn", "publisher", "published_year", "edition", "description", "cover_image", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "published_year": forms.NumberInput(attrs={"placeholder": "e.g., 2024", "min": "1800", "max": "2100"}),
        }


class BookCopyForm(forms.ModelForm):
    class Meta:
        model = BookCopy
        fields = ["book", "copy_code", "barcode", "status", "location", "acquisition_date", "price", "notes", "is_active"]
        widgets = {
            "acquisition_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


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

        if borrower_type == BookLoan.BORROWER_TYPE_STUDENT and not student:
            self.add_error("student", "Student is required for student borrower type.")
        
        if borrower_type == BookLoan.BORROWER_TYPE_STAFF and not staff:
            self.add_error("staff", "Staff is required for staff borrower type.")

        if copy and copy.status != BookCopy.AVAILABLE:
            self.add_error("copy", f"This copy is not available (current status: {copy.get_status_display()}).")

        return cleaned


class CheckInForm(forms.Form):
    copy_code_or_barcode = forms.CharField(max_length=128, label="Copy Code or Barcode", help_text="Scan or enter the book copy code/barcode")


class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ["book", "borrower_type", "student", "staff", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned = super().clean()
        borrower_type = cleaned.get("borrower_type")
        student = cleaned.get("student")
        staff = cleaned.get("staff")

        if borrower_type == Reservation.BORROWER_TYPE_STUDENT and not student:
            self.add_error("student", "Student is required for student borrower type.")
        
        if borrower_type == Reservation.BORROWER_TYPE_STAFF and not staff:
            self.add_error("staff", "Staff is required for staff borrower type.")

        return cleaned


class FineForm(forms.ModelForm):
    class Meta:
        model = Fine
        fields = ["amount", "reason", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2}),
        }
