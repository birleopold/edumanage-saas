from django import forms

from .models import Exam, ExamPaper, ExamQuestion, ExamSchedule, QuestionBank, SeatAllocation, StudentResponse


class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ["term", "name", "exam_mode", "start_date", "end_date", "description", "instructions", "is_active"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "instructions": forms.Textarea(attrs={"rows": 4}),
        }


class ExamPaperForm(forms.ModelForm):
    class Meta:
        model = ExamPaper
        fields = [
            "exam", "offering", "assessment_type", "weighting_component", "linked_assessment",
            "max_score", "passing_score", "weight", "duration_minutes",
            "date", "start_time", "end_time", "instructions", "allow_calculator", "randomize_questions",
            "show_results_immediately", "results_published", "report_cards_enabled", "is_published",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "instructions": forms.Textarea(attrs={"rows": 4}),
        }
        help_texts = {
            "assessment_type": "Optional category used by the configurable assessment framework.",
            "weighting_component": "Optional explicit component; leave blank to resolve by type.",
            "linked_assessment": "Optional compatibility link. Exam scores remain in the exams module.",
            "weight": "Legacy exam-paper weight remains supported when no scheme applies.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.tenant.assessments.models import Assessment, AssessmentType, AssessmentWeightingComponent

        self.fields["assessment_type"].queryset = AssessmentType.objects.filter(is_active=True).order_by("kind", "name")
        components = AssessmentWeightingComponent.objects.filter(
            is_active=True,
            scheme__is_active=True,
            assessment_type__is_active=True,
        ).select_related("scheme", "assessment_type")
        selected_type = self.data.get("assessment_type") if self.is_bound else getattr(self.instance, "assessment_type_id", None)
        if selected_type:
            components = components.filter(assessment_type_id=selected_type)
        self.fields["weighting_component"].queryset = components.order_by("scheme__name", "order")
        assessments = Assessment.objects.select_related("offering", "assessment_type").order_by("offering", "name")
        selected_offering = self.data.get("offering") if self.is_bound else getattr(self.instance, "offering_id", None)
        if selected_offering:
            assessments = assessments.filter(offering_id=selected_offering)
        self.fields["linked_assessment"].queryset = assessments

    def clean(self):
        cleaned = super().clean()
        exam = cleaned.get("exam")
        offering = cleaned.get("offering")
        if exam and offering and offering.term_id != exam.term_id:
            self.add_error("offering", "Offering term must match the exam term.")
        max_score = cleaned.get("max_score")
        passing_score = cleaned.get("passing_score")
        if passing_score and max_score and passing_score > max_score:
            self.add_error("passing_score", "Passing score cannot exceed maximum score.")
        start_time = cleaned.get("start_time")
        end_time = cleaned.get("end_time")
        if start_time and end_time and end_time <= start_time:
            self.add_error("end_time", "End time must be after start time.")
        assessment_type = cleaned.get("assessment_type")
        component = cleaned.get("weighting_component")
        linked_assessment = cleaned.get("linked_assessment")
        if component and assessment_type and component.assessment_type_id != assessment_type.pk:
            self.add_error("weighting_component", "The component must use the selected assessment type.")
        if linked_assessment and offering and linked_assessment.offering_id != offering.pk:
            self.add_error("linked_assessment", "The linked assessment must belong to the same course offering.")
        return cleaned


class QuestionBankForm(forms.ModelForm):
    class Meta:
        model = QuestionBank
        fields = ["course", "question_type", "difficulty", "question_text", "question_image", "marks", "option_a", "option_b", "option_c", "option_d", "correct_option", "correct_answer", "explanation", "tags", "is_active"]
        widgets = {"question_text": forms.Textarea(attrs={"rows": 4}), "correct_answer": forms.Textarea(attrs={"rows": 2}), "explanation": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned = super().clean()
        question_type = cleaned.get("question_type")
        if question_type in [QuestionBank.MCQ, QuestionBank.TRUE_FALSE]:
            option_a = cleaned.get("option_a")
            option_b = cleaned.get("option_b")
            correct_option = cleaned.get("correct_option")
            if not option_a or not option_b:
                raise forms.ValidationError("Options A and B are required for MCQ/True-False questions.")
            if not correct_option:
                raise forms.ValidationError("Correct option must be specified for MCQ/True-False questions.")
            if question_type == QuestionBank.MCQ and correct_option.upper() not in ["A", "B", "C", "D"]:
                self.add_error("correct_option", "For MCQ, correct option must be A, B, C, or D.")
            if question_type == QuestionBank.TRUE_FALSE and correct_option.upper() not in ["A", "B"]:
                self.add_error("correct_option", "For True/False, correct option must be A or B.")
        if question_type == QuestionBank.FILL_BLANK and not cleaned.get("correct_answer"):
            raise forms.ValidationError("Correct answer is required for fill-in-the-blank questions.")
        return cleaned


class ExamQuestionForm(forms.ModelForm):
    class Meta:
        model = ExamQuestion
        fields = ["paper", "question", "order", "marks"]

    def clean(self):
        cleaned = super().clean()
        paper = cleaned.get("paper")
        question = cleaned.get("question")
        if paper and question and question.course_id != paper.offering.course_id:
            self.add_error("question", "Question must belong to the same course as the exam paper.")
        return cleaned


class ExamScheduleForm(forms.ModelForm):
    class Meta:
        model = ExamSchedule
        fields = ["paper", "room_name", "date", "start_time", "end_time", "capacity", "invigilator", "notes"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"}), "start_time": forms.TimeInput(attrs={"type": "time"}), "end_time": forms.TimeInput(attrs={"type": "time"}), "notes": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned = super().clean()
        start_time = cleaned.get("start_time")
        end_time = cleaned.get("end_time")
        if start_time and end_time and end_time <= start_time:
            self.add_error("end_time", "End time must be after start time.")
        capacity = cleaned.get("capacity")
        if capacity and capacity < 1:
            self.add_error("capacity", "Capacity must be at least 1.")
        return cleaned


class SeatAllocationForm(forms.ModelForm):
    class Meta:
        model = SeatAllocation
        fields = ["schedule", "student", "seat_number"]

    def clean(self):
        cleaned = super().clean()
        schedule = cleaned.get("schedule")
        if schedule and schedule.available_seats() <= 0:
            raise forms.ValidationError("No seats available in this schedule.")
        return cleaned


class BulkSeatAllocationForm(forms.Form):
    schedule = forms.ModelChoiceField(queryset=ExamSchedule.objects.all())
    students = forms.ModelMultipleChoiceField(queryset=None, widget=forms.CheckboxSelectMultiple, required=True)
    seat_prefix = forms.CharField(max_length=8, required=False, help_text="Prefix for seat numbers (e.g., 'A-')")

    def __init__(self, *args, **kwargs):
        from apps.tenant.students.models import StudentProfile
        schedule = kwargs.pop("schedule", None)
        super().__init__(*args, **kwargs)
        if schedule:
            self.fields["students"].queryset = StudentProfile.objects.filter(enrollments__offering=schedule.paper.offering, enrollments__status="ACTIVE").distinct()


class StudentResponseForm(forms.ModelForm):
    class Meta:
        model = StudentResponse
        fields = ["selected_option", "answer_text"]
        widgets = {"answer_text": forms.Textarea(attrs={"rows": 4})}
