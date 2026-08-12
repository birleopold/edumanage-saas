from django import forms
from django.db import transaction

from apps.tenant.education_frameworks.models import (
    CampusEducationStage,
    InstitutionEducationProfile,
    LevelStageMapping,
)
from apps.tenant.orgsettings.models import Campus
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


SCHOOL_INSTITUTION_TYPES = {
    InstitutionEducationProfile.ECD,
    InstitutionEducationProfile.PRIMARY,
    InstitutionEducationProfile.SECONDARY,
    InstitutionEducationProfile.MIXED,
}


def _active_profile_for_campus(campus):
    if campus is None:
        return InstitutionEducationProfile.objects.filter(is_active=True).first()
    return InstitutionEducationProfile.objects.filter(
        organization=campus.organization,
        is_active=True,
    ).first()


def _single_active_campus():
    campuses = list(Campus.objects.filter(is_active=True).order_by("pk")[:2])
    return campuses[0] if len(campuses) == 1 else None


class AcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ["name", "start_date", "end_date", "is_current"]
        labels = {
            "name": "Academic year name",
            "is_current": "Use this as the current academic year",
        }
        help_texts = {
            "name": "Use the school wording administrators recognise, for example 2026 or 2026/2027.",
            "is_current": "If selected, EduManage automatically removes the Current flag from every other academic year.",
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g., 2026 or 2026/2027"}),
            "start_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
            "end_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and start > end:
            self.add_error("end_date", "End date must be on or after the academic year start date.")
        return cleaned

    def save(self, commit=True):
        item = super().save(commit=False)
        if not commit:
            return item
        with transaction.atomic():
            if item.is_current:
                AcademicYear.objects.exclude(pk=item.pk).update(is_current=False)
            item.save()
            self._save_m2m()
        return item


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
        labels = {
            "year": "Academic year",
            "name": "Period name",
            "type": "School period type",
            "order": "Sequence in the year",
            "is_current": "Use this as the current term/semester",
        }
        help_texts = {
            "name": "For example Term 1, Term 2 or Semester 1.",
            "order": "Use 1 for the first period, 2 for the second, and so on.",
            "is_current": "If selected, EduManage automatically makes this the only current period and also makes its academic year current.",
        }
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
            "end_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }

    def clean(self):
        cleaned = super().clean()
        year = cleaned.get("year")
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and start > end:
            self.add_error("end_date", "End date must be on or after the period start date.")
        if year and start and year.start_date and start < year.start_date:
            self.add_error("start_date", "This period cannot start before the selected academic year.")
        if year and end and year.end_date and end > year.end_date:
            self.add_error("end_date", "This period cannot end after the selected academic year.")
        return cleaned

    def save(self, commit=True):
        item = super().save(commit=False)
        if not commit:
            return item
        with transaction.atomic():
            if item.is_current:
                AcademicTerm.objects.exclude(pk=item.pk).update(is_current=False)
                AcademicYear.objects.exclude(pk=item.year_id).update(is_current=False)
                AcademicYear.objects.filter(pk=item.year_id).update(is_current=True)
            item.save()
            self._save_m2m()
        return item


class LevelForm(forms.ModelForm):
    class Meta:
        model = Level
        fields = ["name", "order", "is_active"]
        labels = {
            "name": "Level name",
            "order": "Display order",
        }
        help_texts = {
            "name": "Examples: P1, S1, Year 1 or another level name used by the institution.",
            "order": "Controls the order levels appear in lists and progression screens.",
        }


class ProgramForm(forms.ModelForm):
    class Meta:
        model = Program
        fields = ["name", "code", "is_active"]
        help_texts = {
            "code": "Optional short code used on lists and reports.",
        }


class ClassGroupForm(forms.ModelForm):
    class Meta:
        model = ClassGroup
        fields = ["campus", "name", "code", "level", "program", "is_active"]
        labels = {
            "name": "Class / cohort name",
            "code": "Short code (optional)",
            "level": "Academic level",
            "program": "Programme (higher education / programme-based institutions)",
        }
        help_texts = {
            "name": "Use the name staff recognise, for example P1, S2 Blue or Year 1 Nursing.",
            "level": "For ordinary schools, choose the P/S/other level this class belongs to.",
            "program": "Leave blank unless this class belongs to a programme or course of study.",
        }

    def __init__(self, *args, campus=None, **kwargs):
        self.default_campus = campus or _single_active_campus()
        super().__init__(*args, **kwargs)
        campus_qs = Campus.objects.filter(is_active=True).order_by("name")
        if campus is not None:
            campus_qs = campus_qs.filter(pk=campus.pk)
            self.fields["campus"].required = True
            self.fields["campus"].initial = campus
        elif campus_qs.count() > 1:
            self.fields["campus"].required = True
            self.fields["campus"].help_text = "Choose the campus explicitly because this institution has more than one active campus."
        elif self.default_campus is not None:
            self.fields["campus"].initial = self.default_campus
        self.fields["campus"].queryset = campus_qs
        self.fields["level"].queryset = Level.objects.filter(is_active=True).order_by("order", "name")
        self.fields["program"].queryset = Program.objects.filter(is_active=True).order_by("name")

    def clean(self):
        cleaned = super().clean()
        campus = cleaned.get("campus") or self.default_campus
        level = cleaned.get("level")
        program = cleaned.get("program")
        name = str(cleaned.get("name") or "").strip()
        is_active = bool(cleaned.get("is_active"))

        if campus is not None and cleaned.get("campus") is None:
            cleaned["campus"] = campus

        profile = _active_profile_for_campus(campus)
        if profile and profile.institution_type in SCHOOL_INSTITUTION_TYPES:
            if not level:
                self.add_error("level", "Choose the academic level for this school class before saving.")
            else:
                mapping = LevelStageMapping.objects.filter(
                    profile=profile,
                    legacy_level_id=level.pk,
                ).select_related("stage").first()
                if mapping is None:
                    self.add_error(
                        "level",
                        "This level is not connected to an education stage yet. Return to School Setup and synchronize the education structure first.",
                    )
                elif campus and not CampusEducationStage.objects.filter(
                    profile=profile,
                    campus=campus,
                    stage_id=mapping.stage_id,
                    is_active=True,
                    stage__is_active=True,
                ).exists():
                    self.add_error(
                        "level",
                        f"{level} belongs to {mapping.stage}, but that education stage is not enabled for {campus}. Review Education Structure first.",
                    )

        if program and not program.is_active:
            self.add_error("program", "Choose an active programme.")

        if is_active and name:
            duplicate = ClassGroup.objects.filter(
                is_active=True,
                name__iexact=name,
                campus=campus,
            )
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                self.add_error("name", "An active class/cohort with this name already exists in the selected campus.")
        return cleaned


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ["name", "code", "level", "program", "credits", "is_active"]
        labels = {
            "name": "Subject / course unit name",
            "code": "Subject / course code (optional)",
            "level": "Default level (optional)",
            "program": "Programme (optional)",
            "credits": "Credits (higher education, optional)",
        }
        help_texts = {
            "level": "Leave blank when the same subject is offered across several levels; choose a level only when this record is level-specific.",
            "program": "Leave blank for ordinary school subjects unless the subject/course unit belongs to a programme.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["level"].queryset = Level.objects.filter(is_active=True).order_by("order", "name")
        self.fields["program"].queryset = Program.objects.filter(is_active=True).order_by("name")

    def clean(self):
        cleaned = super().clean()
        name = str(cleaned.get("name") or "").strip()
        code = str(cleaned.get("code") or "").strip()
        level = cleaned.get("level")
        program = cleaned.get("program")
        is_active = bool(cleaned.get("is_active"))
        if not is_active:
            return cleaned

        duplicate = Course.objects.filter(
            is_active=True,
            name__iexact=name,
            level=level,
            program=program,
        )
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if name and duplicate.exists():
            self.add_error("name", "An active subject/course with this name and the same level/programme scope already exists.")

        if code:
            duplicate_code = Course.objects.filter(is_active=True, code__iexact=code)
            if self.instance.pk:
                duplicate_code = duplicate_code.exclude(pk=self.instance.pk)
            if duplicate_code.exists():
                self.add_error("code", "This code is already used by another active subject/course. Use one clear code per subject record.")
        return cleaned


class CourseOfferingForm(forms.ModelForm):
    class Meta:
        model = CourseOffering
        fields = ["campus", "course", "term", "class_group", "teacher", "is_active"]
        labels = {
            "course": "Subject / course unit",
            "term": "Academic period",
            "class_group": "Class / cohort",
            "teacher": "Teacher (can be assigned later)",
        }
        help_texts = {
            "term": "Choose the term/semester in which this subject is actually taught.",
            "class_group": "For ordinary schools, choose the class taking this subject.",
            "teacher": "Leave blank only if the teacher assignment is not known yet; School Setup will keep this step incomplete until assigned.",
        }

    def __init__(self, *args, **kwargs):
        campus = kwargs.pop("campus", None)
        self.campus_scope = campus or _single_active_campus()
        super().__init__(*args, **kwargs)

        self.fields["course"].queryset = Course.objects.filter(is_active=True).order_by("name")
        self.fields["term"].queryset = AcademicTerm.objects.select_related("year").order_by(
            "-is_current", "-year__name", "order"
        )
        class_qs = ClassGroup.objects.filter(is_active=True).select_related("campus", "level").order_by("name")
        teacher_qs = TeacherProfile.objects.filter(is_active=True).select_related("campus").order_by("last_name", "first_name")
        campus_qs = Campus.objects.filter(is_active=True).order_by("name")
        if campus is not None:
            class_qs = class_qs.filter(campus=campus)
            teacher_qs = teacher_qs.filter(campus=campus)
            campus_qs = campus_qs.filter(pk=campus.pk)
            self.fields["campus"].initial = campus
            self.fields["campus"].required = True
        elif self.campus_scope is not None:
            self.fields["campus"].initial = self.campus_scope
        elif campus_qs.count() > 1:
            self.fields["campus"].required = True
            self.fields["campus"].help_text = "Choose a campus first so class and teacher scope is unambiguous."
        self.fields["campus"].queryset = campus_qs
        self.fields["class_group"].queryset = class_qs
        self.fields["teacher"].queryset = teacher_qs
        current_term = AcademicTerm.objects.filter(is_current=True).order_by("pk").first()
        if current_term and not self.instance.pk:
            self.fields["term"].initial = current_term

    def clean(self):
        cleaned = super().clean()
        campus = cleaned.get("campus") or self.campus_scope
        course = cleaned.get("course")
        term = cleaned.get("term")
        class_group = cleaned.get("class_group")
        teacher = cleaned.get("teacher")
        is_active = bool(cleaned.get("is_active"))
        if campus is not None and cleaned.get("campus") is None:
            cleaned["campus"] = campus

        profile = _active_profile_for_campus(campus)
        if profile and profile.institution_type in SCHOOL_INSTITUTION_TYPES and not class_group:
            self.add_error("class_group", "Choose the school class taking this subject/course.")

        if class_group:
            if not class_group.is_active:
                self.add_error("class_group", "Choose an active class/cohort.")
            if campus and class_group.campus_id and class_group.campus_id != campus.pk:
                self.add_error("class_group", "The selected class belongs to a different campus.")
            if course and course.level_id and class_group.level_id and course.level_id != class_group.level_id:
                self.add_error(
                    "course",
                    f"{course} is level-specific to {course.level}, but the selected class belongs to {class_group.level}.",
                )

        if teacher:
            if not teacher.is_active:
                self.add_error("teacher", "Choose an active teacher.")
            if campus and teacher.campus_id and teacher.campus_id != campus.pk:
                self.add_error("teacher", "The selected teacher belongs to a different campus.")

        if is_active and course and term:
            duplicate = CourseOffering.objects.filter(
                is_active=True,
                campus=campus,
                course=course,
                term=term,
                class_group=class_group,
            )
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                self.add_error(
                    None,
                    "This active subject offering already exists for the same campus, class and academic period.",
                )
        return cleaned


class EnrollmentForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ["offering", "student", "status"]
        labels = {
            "offering": "Subject / class offering",
            "student": "Learner",
        }

    def __init__(self, *args, **kwargs):
        campus = kwargs.pop("campus", None)
        super().__init__(*args, **kwargs)
        offerings = CourseOffering.objects.filter(is_active=True).select_related("course", "term", "class_group")
        students = StudentProfile.objects.filter(is_active=True).order_by("last_name", "first_name")
        if campus is not None:
            offerings = offerings.filter(campus=campus)
            students = students.filter(campus=campus)
        self.fields["offering"].queryset = offerings
        self.fields["student"].queryset = students


class GradingScaleForm(forms.ModelForm):
    class Meta:
        model = GradingScale
        fields = ["name", "description", "is_default", "is_active"]
        help_texts = {
            "is_default": "The default scale is used when no more specific grading rule applies. Only one scale can be default.",
        }


class GradeRangeForm(forms.ModelForm):
    class Meta:
        model = GradeRange
        fields = ["scale", "grade", "min_score", "max_score", "grade_point", "remark", "order"]
        labels = {
            "min_score": "Minimum percentage",
            "max_score": "Maximum percentage",
            "order": "Display order",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["scale"].queryset = GradingScale.objects.filter(is_active=True).order_by("-is_default", "name")

    def clean(self):
        cleaned = super().clean()
        scale = cleaned.get("scale")
        minimum = cleaned.get("min_score")
        maximum = cleaned.get("max_score")
        if minimum is None or maximum is None:
            return cleaned
        if minimum < 0 or maximum > 100:
            self.add_error("min_score" if minimum < 0 else "max_score", "Grade percentages must stay between 0 and 100.")
        if minimum > maximum:
            self.add_error("max_score", "Maximum percentage must be greater than or equal to the minimum percentage.")
        if scale and minimum <= maximum:
            overlap = GradeRange.objects.filter(
                scale=scale,
                min_score__lte=maximum,
                max_score__gte=minimum,
            )
            if self.instance.pk:
                overlap = overlap.exclude(pk=self.instance.pk)
            if overlap.exists():
                self.add_error(
                    None,
                    "This percentage range overlaps another grade in the same scale. Adjust the minimum or maximum so every score has one clear grade.",
                )
        return cleaned


class StreamForm(forms.ModelForm):
    class Meta:
        model = Stream
        fields = ["class_group", "name", "capacity", "class_teacher", "room", "is_active"]
        labels = {
            "class_group": "Class",
            "name": "Stream name",
            "class_teacher": "Class teacher (optional)",
        }
        help_texts = {
            "name": "Examples: Blue, East, A. Do not create streams if the school does not use them.",
            "capacity": "Maximum intended number of learners in this stream.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["class_group"].queryset = ClassGroup.objects.filter(is_active=True).select_related("campus").order_by("name")
        self.fields["class_teacher"].queryset = TeacherProfile.objects.filter(is_active=True).select_related("campus").order_by("last_name", "first_name")

    def clean(self):
        cleaned = super().clean()
        class_group = cleaned.get("class_group")
        teacher = cleaned.get("class_teacher")
        capacity = cleaned.get("capacity")
        if capacity is not None and capacity < 1:
            self.add_error("capacity", "Capacity must be at least 1 learner.")
        if class_group and teacher and class_group.campus_id and teacher.campus_id and class_group.campus_id != teacher.campus_id:
            self.add_error("class_teacher", "Choose a class teacher from the same campus as the class.")
        return cleaned
