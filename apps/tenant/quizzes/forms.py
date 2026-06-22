from django import forms

from apps.tenant.academics.models import ClassGroup, CourseOffering
from apps.tenant.students.models import StudentProfile

from .models import Quiz, QuizAnswer, QuizQuestion, QuizQuestionChoice


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


class QuizForm(StyledFormMixin, forms.ModelForm):
    assign_class_group = forms.ModelChoiceField(queryset=ClassGroup.objects.filter(is_active=True), required=False, help_text="Optional: assign all active students in this class.")

    class Meta:
        model = Quiz
        fields = [
            "name",
            "topic",
            "description",
            "campus",
            "course_offering",
            "time_limit_minutes",
            "passing_score_percentage",
            "difficulty",
            "available_from",
            "available_until",
            "students",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "available_from": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "available_until": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "students": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        offerings = CourseOffering.objects.select_related("course", "term", "teacher", "class_group", "campus").filter(is_active=True)
        if teacher:
            offerings = offerings.filter(teacher=teacher)
        self.fields["course_offering"].queryset = offerings.order_by("course__name")
        self.fields["students"].queryset = StudentProfile.objects.filter(is_active=True).order_by("last_name", "first_name")
        self._style_fields()

    def save(self, commit=True):
        quiz = super().save(commit=commit)
        if commit:
            self.save_m2m()
            class_group = self.cleaned_data.get("assign_class_group")
            if class_group:
                students = StudentProfile.objects.filter(stream__class_group=class_group, is_active=True)
                quiz.students.add(*students)
        return quiz


class QuestionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = QuizQuestion
        fields = ["question_text", "question_type", "points", "order", "correct_answer"]
        widgets = {
            "question_text": forms.Textarea(attrs={"rows": 4}),
            "correct_answer": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class ChoiceForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = QuizQuestionChoice
        fields = ["choice_text", "is_correct", "order"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class QuizSubmitForm(forms.Form):
    def __init__(self, *args, quiz=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.quiz = quiz
        for question in quiz.get_questions().prefetch_related("choices"):
            field_name = f"question_{question.id}"
            if question.question_type == QuizQuestion.MULTIPLE_CHOICE:
                self.fields[field_name] = forms.ModelChoiceField(
                    queryset=question.choices.all(),
                    required=False,
                    widget=forms.RadioSelect,
                    label=question.question_text,
                )
            elif question.question_type == QuizQuestion.TRUE_FALSE:
                self.fields[field_name] = forms.ChoiceField(
                    choices=(("True", "True"), ("False", "False")),
                    required=False,
                    widget=forms.RadioSelect,
                    label=question.question_text,
                )
            else:
                self.fields[field_name] = forms.CharField(
                    required=False,
                    widget=forms.Textarea(attrs={"rows": 4, "class": StyledFormMixin.field_class}),
                    label=question.question_text,
                )
            self.fields[field_name].question = question


class GradeAnswerForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = QuizAnswer
        fields = ["is_correct", "points_earned", "feedback"]
        widgets = {"feedback": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
