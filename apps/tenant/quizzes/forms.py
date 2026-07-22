from django import forms

from apps.tenant.academics.models import ClassGroup, CourseOffering, Enrollment
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
                field.widget.attrs.setdefault(
                    "class",
                    "h-5 w-5 rounded border-slate-300 text-primary-600 focus:ring-primary-500",
                )
            elif isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs.setdefault("class", "space-y-2")
            else:
                field.widget.attrs.setdefault("class", self.field_class)


class QuizForm(StyledFormMixin, forms.ModelForm):
    assign_class_group = forms.ModelChoiceField(
        queryset=ClassGroup.objects.none(),
        required=False,
        help_text="Optional: assign all active students in this class.",
    )

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

    def __init__(self, *args, teacher=None, campus_scope=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.teacher = teacher
        self.campus_scope = campus_scope

        offerings = CourseOffering.objects.select_related(
            "course",
            "term",
            "teacher",
            "class_group",
            "campus",
        ).filter(is_active=True)
        class_groups = ClassGroup.objects.filter(is_active=True)
        students = StudentProfile.objects.filter(is_active=True)
        campuses = self.fields["campus"].queryset.filter(is_active=True)

        if teacher is not None:
            offerings = offerings.filter(teacher=teacher)
            enrollment_students = Enrollment.objects.filter(
                offering__teacher=teacher,
                status=Enrollment.ACTIVE,
            ).values("student_id")
            students = students.filter(pk__in=enrollment_students)
            class_groups = class_groups.filter(
                pk__in=offerings.exclude(class_group__isnull=True).values("class_group_id")
            )
            campuses = campuses.filter(
                pk__in=offerings.exclude(campus__isnull=True).values("campus_id")
            )

        if campus_scope is not None:
            offerings = offerings.filter(campus=campus_scope)
            class_groups = class_groups.filter(campus=campus_scope)
            students = students.filter(campus=campus_scope)
            campuses = campuses.filter(pk=campus_scope.pk)
            self.initial.setdefault("campus", campus_scope)

        self.fields["campus"].queryset = campuses.order_by("name")
        self.fields["course_offering"].queryset = offerings.order_by("course__name")
        self.fields["assign_class_group"].queryset = class_groups.order_by("name")
        self.fields["students"].queryset = students.distinct().order_by("last_name", "first_name")
        self._style_fields()

    def clean(self):
        cleaned = super().clean()
        offering = cleaned.get("course_offering")
        campus = cleaned.get("campus")
        class_group = cleaned.get("assign_class_group")
        selected_students = cleaned.get("students")

        effective_campus = campus or getattr(offering, "campus", None) or self.campus_scope
        if effective_campus is not None:
            cleaned["campus"] = effective_campus

        if self.campus_scope is not None and (
            effective_campus is None or effective_campus.pk != self.campus_scope.pk
        ):
            self.add_error("campus", "Choose the campus assigned to your account.")

        if offering and offering.campus_id and effective_campus and offering.campus_id != effective_campus.pk:
            self.add_error("course_offering", "The course offering belongs to a different campus.")

        if class_group and class_group.campus_id and effective_campus and class_group.campus_id != effective_campus.pk:
            self.add_error("assign_class_group", "The selected class belongs to a different campus.")

        if selected_students is not None and effective_campus:
            if selected_students.exclude(campus_id=effective_campus.pk).exists():
                self.add_error("students", "Every selected learner must belong to the quiz campus.")

        time_limit = cleaned.get("time_limit_minutes")
        if time_limit is not None and time_limit <= 0:
            self.add_error("time_limit_minutes", "Time limit must be greater than zero.")

        passing_score = cleaned.get("passing_score_percentage")
        if passing_score is not None and not 0 <= passing_score <= 100:
            self.add_error("passing_score_percentage", "Passing score must be between 0 and 100.")

        available_from = cleaned.get("available_from")
        available_until = cleaned.get("available_until")
        if available_from and available_until and available_from >= available_until:
            self.add_error("available_until", "Availability must end after it starts.")

        return cleaned

    def assign_class_group_students(self, quiz):
        class_group = self.cleaned_data.get("assign_class_group")
        if not class_group:
            return
        students = StudentProfile.objects.filter(
            stream__class_group=class_group,
            is_active=True,
        )
        if quiz.campus_id:
            students = students.filter(campus_id=quiz.campus_id)
        quiz.students.add(*students)


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
