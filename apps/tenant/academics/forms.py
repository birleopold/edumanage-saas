from django import forms

from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile

from .models import (
    AcademicTerm,
    AcademicYear,
    ClassGroup,
    Course,
    CourseOffering,
    Enrollment,
    GradeRange,
    GradingScale,
    Level,
    Program,
    Stream,
)


class AcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ["name", "start_date", "end_date", "is_current"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g., 2024-2025"}),
            "start_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
            "end_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }


class AcademicTermForm(forms.ModelForm):
    class Meta:
        model = AcademicTerm
        fields = [
            "year",
            "name",
            "type",
            "order",
            "start_date",
            "end_date",
            "is_current",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
            "end_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }


class LevelForm(forms.ModelForm):
    class Meta:
        model = Level
        fields = ["name", "order", "is_active"]


class ProgramForm(forms.ModelForm):
    class Meta:
        model = Program
        fields = ["name", "code", "is_active"]


class ClassGroupForm(forms.ModelForm):
    class Meta:
        model = ClassGroup
        fields = ["campus", "name", "code", "level", "program", "is_active"]


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ["name", "code", "level", "program", "credits", "is_active"]


class CourseOfferingForm(forms.ModelForm):
    class Meta:
        model = CourseOffering
        fields = ["campus", "course", "term", "class_group", "teacher", "is_active"]

    def __init__(self, *args, **kwargs):
        campus = kwargs.pop("campus", None)
        super().__init__(*args, **kwargs)
        if campus is not None:
            self.fields["class_group"].queryset = ClassGroup.objects.filter(campus=campus)
            self.fields["teacher"].queryset = TeacherProfile.objects.filter(campus=campus)


class EnrollmentForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ["offering", "student", "status"]

    def __init__(self, *args, **kwargs):
        campus = kwargs.pop("campus", None)
        super().__init__(*args, **kwargs)
        if campus is not None:
            self.fields["offering"].queryset = CourseOffering.objects.filter(campus=campus)
            self.fields["student"].queryset = StudentProfile.objects.filter(campus=campus)


class GradingScaleForm(forms.ModelForm):
    class Meta:
        model = GradingScale
        fields = ["name", "description", "is_default", "is_active"]


class GradeRangeForm(forms.ModelForm):
    class Meta:
        model = GradeRange
        fields = ["scale", "grade", "min_score", "max_score", "grade_point", "remark", "order"]


class StreamForm(forms.ModelForm):
    class Meta:
        model = Stream
        fields = ["class_group", "name", "capacity", "class_teacher", "room", "is_active"]
