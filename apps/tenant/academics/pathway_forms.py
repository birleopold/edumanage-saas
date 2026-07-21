from django import forms
from django.db.models import Q

from .models import (
    AcademicTerm,
    ClassGroup,
    ClassGroupPathwayAssignment,
    Course,
    ProgrammePathway,
    ProgrammePathwayLevel,
    SubjectCombination,
    SubjectCombinationCourse,
    normalize_academic_code,
)


class ProgrammePathwayForm(forms.ModelForm):
    class Meta:
        model = ProgrammePathway
        fields = [
            "code",
            "name",
            "description",
            "program",
            "campus",
            "stage",
            "priority",
            "is_default",
            "is_active",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}
        help_texts = {
            "priority": "Higher priority wins when more than one pathway applies.",
            "is_default": "Used as a tie-breaker after scope and priority.",
        }

    def clean_code(self):
        return normalize_academic_code(self.cleaned_data.get("code"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["program"].queryset = self.fields["program"].queryset.filter(is_active=True)


class ProgrammePathwayLevelForm(forms.ModelForm):
    class Meta:
        model = ProgrammePathwayLevel
        fields = ["level", "sequence", "minimum_terms", "is_entry", "is_exit", "is_active"]

    def __init__(self, *args, pathway=None, **kwargs):
        self.pathway = pathway
        super().__init__(*args, **kwargs)
        used = ProgrammePathwayLevel.objects.none()
        if pathway:
            used = pathway.pathway_levels.exclude(pk=self.instance.pk).values_list("level_id", flat=True)
            self.fields["level"].queryset = self.fields["level"].queryset.filter(is_active=True).exclude(pk__in=used)

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.pathway:
            obj.pathway = self.pathway
        if commit:
            obj.full_clean()
            obj.save()
        return obj


class SubjectCombinationForm(forms.ModelForm):
    class Meta:
        model = SubjectCombination
        fields = [
            "code",
            "name",
            "description",
            "level",
            "minimum_subjects",
            "maximum_subjects",
            "priority",
            "is_default",
            "is_active",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, pathway=None, **kwargs):
        self.pathway = pathway
        super().__init__(*args, **kwargs)
        if pathway:
            level_ids = pathway.pathway_levels.filter(is_active=True).values_list("level_id", flat=True)
            self.fields["level"].queryset = self.fields["level"].queryset.filter(pk__in=level_ids, is_active=True)

    def clean_code(self):
        return normalize_academic_code(self.cleaned_data.get("code"))

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.pathway:
            obj.pathway = self.pathway
        if commit:
            obj.full_clean()
            obj.save()
        return obj


class SubjectCombinationCourseForm(forms.ModelForm):
    class Meta:
        model = SubjectCombinationCourse
        fields = ["course", "role", "subject_group", "order", "is_active"]

    def __init__(self, *args, combination=None, **kwargs):
        self.combination = combination
        super().__init__(*args, **kwargs)
        courses = Course.objects.filter(is_active=True)
        if combination:
            used = combination.course_memberships.exclude(pk=self.instance.pk).values_list("course_id", flat=True)
            program_id = combination.pathway.program_id
            courses = courses.filter(Q(program_id=program_id) | Q(program__isnull=True)).exclude(pk__in=used)
        self.fields["course"].queryset = courses.order_by("name")

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.combination:
            obj.combination = self.combination
        if commit:
            obj.full_clean()
            obj.save()
        return obj


class ClassGroupPathwayAssignmentForm(forms.ModelForm):
    class Meta:
        model = ClassGroupPathwayAssignment
        fields = ["class_group", "pathway", "subject_combination", "academic_term", "is_active"]
        help_texts = {
            "academic_term": "Leave blank for a standing assignment across terms.",
            "subject_combination": "Leave blank to use the best matching default combination.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["class_group"].queryset = ClassGroup.objects.filter(is_active=True).select_related(
            "campus", "level", "program"
        ).order_by("name")
        self.fields["pathway"].queryset = ProgrammePathway.objects.filter(is_active=True).select_related(
            "program", "campus", "stage"
        ).order_by("name")
        combinations = SubjectCombination.objects.filter(is_active=True).select_related("pathway", "level")
        pathway_id = None
        if self.is_bound:
            pathway_id = self.data.get("pathway")
        elif self.instance and self.instance.pathway_id:
            pathway_id = self.instance.pathway_id
        if pathway_id:
            combinations = combinations.filter(pathway_id=pathway_id)
        self.fields["subject_combination"].queryset = combinations.order_by("pathway__name", "name")
        self.fields["academic_term"].queryset = AcademicTerm.objects.select_related("year").order_by(
            "-year__name", "order"
        )


class OfferingPlanForm(forms.Form):
    class_group = forms.ModelChoiceField(
        queryset=ClassGroup.objects.none(),
        help_text="Choose an existing class group with a Phase 5 pathway assignment.",
    )
    term = forms.ModelChoiceField(queryset=AcademicTerm.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["class_group"].queryset = ClassGroup.objects.filter(is_active=True).select_related(
            "campus", "level", "program"
        ).order_by("name")
        self.fields["term"].queryset = AcademicTerm.objects.select_related("year").order_by(
            "-year__name", "order"
        )
