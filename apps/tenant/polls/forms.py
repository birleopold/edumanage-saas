from django import forms

from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile

from .models import Poll, PollOption


class StyledFormMixin:
    field_class = (
        "block w-full rounded-xl border-2 border-slate-200 bg-white px-4 py-2.5 text-sm "
        "font-semibold text-slate-900 outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-100"
    )

    def _style_fields(self):
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault(
                    "class",
                    "h-5 w-5 rounded border-slate-300 text-primary-600 focus:ring-primary-500",
                )
            elif isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs.setdefault("class", "space-y-2")
            else:
                field.widget.attrs.setdefault("class", self.field_class)


class PollForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Poll
        fields = [
            "title",
            "description",
            "campus",
            "audience",
            "specific_students",
            "specific_teachers",
            "is_anonymous",
            "allow_multiple_votes",
            "show_results_before_voting",
            "available_from",
            "available_until",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "specific_students": forms.CheckboxSelectMultiple(),
            "specific_teachers": forms.CheckboxSelectMultiple(),
            "available_from": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "available_until": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, campus_scope=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.campus_scope = campus_scope

        campuses = self.fields["campus"].queryset.filter(is_active=True)
        students = StudentProfile.objects.filter(is_active=True)
        teachers = TeacherProfile.objects.filter(is_active=True)
        if campus_scope is not None:
            campuses = campuses.filter(pk=campus_scope.pk)
            students = students.filter(campus=campus_scope)
            teachers = teachers.filter(campus=campus_scope)
            self.initial.setdefault("campus", campus_scope)

        self.fields["campus"].queryset = campuses.order_by("name")
        self.fields["specific_students"].queryset = students.order_by("last_name", "first_name")
        self.fields["specific_teachers"].queryset = teachers.order_by("last_name", "first_name")
        self._style_fields()

    def clean(self):
        cleaned = super().clean()
        campus = cleaned.get("campus") or self.campus_scope
        students = cleaned.get("specific_students")
        teachers = cleaned.get("specific_teachers")

        if campus is not None:
            cleaned["campus"] = campus

        if self.campus_scope is not None and (
            campus is None or campus.pk != self.campus_scope.pk
        ):
            self.add_error("campus", "Choose the campus assigned to your account.")

        if campus and students is not None and students.exclude(campus_id=campus.pk).exists():
            self.add_error("specific_students", "Every selected learner must belong to the poll campus.")
        if campus and teachers is not None and teachers.exclude(campus_id=campus.pk).exists():
            self.add_error("specific_teachers", "Every selected teacher must belong to the poll campus.")

        available_from = cleaned.get("available_from")
        available_until = cleaned.get("available_until")
        if available_from and available_until and available_from >= available_until:
            self.add_error("available_until", "Availability must end after it starts.")

        return cleaned


class PollOptionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = PollOption
        fields = ["option_text", "order"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class PollVoteForm(forms.Form):
    option = forms.ModelChoiceField(
        queryset=PollOption.objects.none(),
        widget=forms.RadioSelect,
        empty_label=None,
    )

    def __init__(self, *args, poll=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["option"].queryset = poll.options.all()
