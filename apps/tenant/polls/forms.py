from django import forms

from .models import Poll, PollOption


class StyledFormMixin:
    field_class = (
        "block w-full rounded-xl border-2 border-slate-200 bg-white px-4 py-2.5 text-sm "
        "font-semibold text-slate-900 outline-none focus:border-primary-500 focus:ring-4 focus:ring-primary-100"
    )

    def _style_fields(self):
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "h-5 w-5 rounded border-slate-300 text-primary-600 focus:ring-primary-500")
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class PollOptionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = PollOption
        fields = ["option_text", "order"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class PollVoteForm(forms.Form):
    option = forms.ModelChoiceField(queryset=PollOption.objects.none(), widget=forms.RadioSelect, empty_label=None)

    def __init__(self, *args, poll=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["option"].queryset = poll.options.all()
