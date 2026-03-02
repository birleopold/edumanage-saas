from django import forms

from .models import Book, BookCopy, BookLoan


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ["title", "author", "isbn", "published_year", "is_active"]
        widgets = {
            "published_year": forms.NumberInput(attrs={"placeholder": "e.g., 2024", "min": "1800", "max": "2100"}),
        }


class BookCopyForm(forms.ModelForm):
    class Meta:
        model = BookCopy
        fields = ["book", "copy_code", "status", "is_active"]


class BookLoanForm(forms.ModelForm):
    class Meta:
        model = BookLoan
        fields = ["copy", "student", "due_date", "returned_at", "status", "note"]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
            "returned_at": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }

    def clean(self):
        cleaned = super().clean()
        copy = cleaned.get("copy")
        status = cleaned.get("status")
        returned_at = cleaned.get("returned_at")

        if status == BookLoan.RETURNED and not returned_at:
            self.add_error("returned_at", "Returned date is required when status is Returned.")

        if copy and (status == BookLoan.OPEN):
            qs = BookLoan.objects.filter(copy=copy, status=BookLoan.OPEN)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("copy", "This copy is already on an open loan.")

        return cleaned
