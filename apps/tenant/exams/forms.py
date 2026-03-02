from django import forms

from .models import Exam, ExamPaper


class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ["term", "name", "start_date", "end_date", "is_active"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
            "end_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }


class ExamPaperForm(forms.ModelForm):
    class Meta:
        model = ExamPaper
        fields = ["exam", "offering", "max_score", "weight", "date", "is_published"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }

    def clean(self):
        cleaned = super().clean()
        exam = cleaned.get("exam")
        offering = cleaned.get("offering")
        if exam and offering and offering.term_id != exam.term_id:
            self.add_error("offering", "Offering term must match the exam term.")
        return cleaned
