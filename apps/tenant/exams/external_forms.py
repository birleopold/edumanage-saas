from django import forms

from apps.tenant.academics.models import Course

from .external_models import (
    ExternalCandidate,
    ExternalCandidateSubject,
    ExternalExamBoard,
    ExternalExamCentre,
    ExternalExamSession,
    ExternalExamSubject,
    normalize_external_code,
)
from .external_services import eligible_students
from .models import Exam, ExamPaper


class ExternalExamBoardForm(forms.ModelForm):
    class Meta:
        model = ExternalExamBoard
        fields = [
            "code",
            "name",
            "board_type",
            "country_code",
            "website",
            "contact_email",
            "candidate_number_label",
            "subject_code_label",
            "is_active",
        ]

    def clean_code(self):
        return normalize_external_code(self.cleaned_data.get("code"))


class ExternalExamCentreForm(forms.ModelForm):
    class Meta:
        model = ExternalExamCentre
        fields = [
            "board",
            "campus",
            "code",
            "name",
            "address",
            "contact_name",
            "contact_phone",
            "is_active",
        ]
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}

    def clean_code(self):
        return normalize_external_code(self.cleaned_data.get("code"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["board"].queryset = ExternalExamBoard.objects.filter(is_active=True).order_by("name")


class ExternalExamSessionForm(forms.ModelForm):
    class Meta:
        model = ExternalExamSession
        fields = [
            "board",
            "centre",
            "code",
            "name",
            "academic_year",
            "campus",
            "stage",
            "level",
            "program",
            "linked_exam",
            "registration_opens",
            "registration_closes",
            "exam_starts",
            "exam_ends",
            "status",
            "candidate_prefix",
            "candidate_number_padding",
            "is_active",
        ]
        widgets = {
            "registration_opens": forms.DateInput(attrs={"type": "date"}),
            "registration_closes": forms.DateInput(attrs={"type": "date"}),
            "exam_starts": forms.DateInput(attrs={"type": "date"}),
            "exam_ends": forms.DateInput(attrs={"type": "date"}),
        }
        help_texts = {
            "linked_exam": "Optional link to an existing internal exam. Internal papers and scores remain unchanged.",
            "candidate_prefix": "Example: UACE-2026-. Leave blank to use the session code.",
        }

    def clean_code(self):
        return normalize_external_code(self.cleaned_data.get("code"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["board"].queryset = ExternalExamBoard.objects.filter(is_active=True).order_by("name")
        board_id = self.data.get("board") if self.is_bound else getattr(self.instance, "board_id", None)
        centres = ExternalExamCentre.objects.filter(is_active=True).select_related("board", "campus")
        if board_id:
            centres = centres.filter(board_id=board_id)
        self.fields["centre"].queryset = centres.order_by("board__name", "code")
        exams = Exam.objects.select_related("term", "term__year").order_by("-term__year__name", "term__order", "name")
        academic_year_id = self.data.get("academic_year") if self.is_bound else getattr(self.instance, "academic_year_id", None)
        if academic_year_id:
            exams = exams.filter(term__year_id=academic_year_id)
        self.fields["linked_exam"].queryset = exams


class ExternalExamSubjectForm(forms.ModelForm):
    class Meta:
        model = ExternalExamSubject
        fields = [
            "course",
            "subject_code",
            "display_name",
            "linked_paper",
            "max_score",
            "is_compulsory",
            "order",
            "is_active",
        ]
        help_texts = {
            "linked_paper": "Optional internal-paper link. Existing internal scores are not copied.",
            "is_compulsory": "Compulsory subjects can be registered in bulk for all active candidates.",
        }

    def __init__(self, *args, session=None, **kwargs):
        self.session = session
        super().__init__(*args, **kwargs)
        courses = Course.objects.filter(is_active=True)
        if session:
            used = session.subjects.exclude(pk=self.instance.pk).values_list("course_id", flat=True)
            if session.program_id:
                from django.db.models import Q

                courses = courses.filter(Q(program_id=session.program_id) | Q(program__isnull=True))
            if session.level_id:
                from django.db.models import Q

                courses = courses.filter(Q(level_id=session.level_id) | Q(level__isnull=True))
            courses = courses.exclude(pk__in=used)
        self.fields["course"].queryset = courses.order_by("name")
        papers = ExamPaper.objects.select_related("exam", "offering__course").order_by("exam", "offering__course__name")
        if session and session.linked_exam_id:
            papers = papers.filter(exam_id=session.linked_exam_id)
        selected_course = self.data.get("course") if self.is_bound else getattr(self.instance, "course_id", None)
        if selected_course:
            papers = papers.filter(offering__course_id=selected_course)
        self.fields["linked_paper"].queryset = papers

    def clean_subject_code(self):
        return normalize_external_code(self.cleaned_data.get("subject_code"))

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.session:
            obj.session = self.session
        if commit:
            obj.full_clean()
            obj.save()
        return obj


class ExternalCandidateForm(forms.ModelForm):
    class Meta:
        model = ExternalCandidate
        fields = [
            "student",
            "centre",
            "candidate_number",
            "board_reference",
            "status",
            "registration_date",
            "accommodations",
            "notes",
            "is_active",
        ]
        widgets = {
            "registration_date": forms.DateInput(attrs={"type": "date"}),
            "accommodations": forms.Textarea(attrs={"rows": 3, "placeholder": '{"extra_time_minutes": 30}'}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, session=None, **kwargs):
        self.session = session
        super().__init__(*args, **kwargs)
        students = eligible_students(session) if session else []
        student_ids = [item.pk for item in students]
        queryset = self.fields["student"].queryset.filter(pk__in=student_ids)
        if session:
            used = session.candidates.exclude(pk=self.instance.pk).values_list("student_id", flat=True)
            queryset = queryset.exclude(pk__in=used)
            self.fields["centre"].queryset = ExternalExamCentre.objects.filter(
                board=session.board,
                is_active=True,
            ).order_by("code")
            if session.centre_id:
                self.fields["centre"].initial = session.centre
        self.fields["student"].queryset = queryset.order_by("last_name", "first_name")

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.session:
            obj.session = self.session
        if commit:
            obj.full_clean()
            obj.save()
        return obj


class ExternalCandidateSubjectForm(forms.ModelForm):
    class Meta:
        model = ExternalCandidateSubject
        fields = ["subject", "status", "paper_reference"]

    def __init__(self, *args, candidate=None, **kwargs):
        self.candidate = candidate
        super().__init__(*args, **kwargs)
        subjects = ExternalExamSubject.objects.none()
        if candidate:
            used = candidate.subject_registrations.exclude(pk=self.instance.pk).values_list("subject_id", flat=True)
            subjects = candidate.session.subjects.filter(is_active=True).exclude(pk__in=used)
        self.fields["subject"].queryset = subjects.order_by("order", "course__name")

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.candidate:
            obj.candidate = self.candidate
        if commit:
            obj.full_clean()
            obj.save()
        return obj


class ExternalResultImportForm(forms.Form):
    csv_file = forms.FileField(
        help_text="UTF-8 CSV with candidate_number and subject_code. Optional columns: score, percentage, grade, result_status and source_reference."
    )
    dry_run = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Validate and preview the file without changing official external results.",
    )
