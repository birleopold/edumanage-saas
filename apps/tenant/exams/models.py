import json
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Exam(models.Model):
    PAPER_BASED = "PAPER_BASED"
    ONLINE = "ONLINE"
    HYBRID = "HYBRID"

    EXAM_MODE_CHOICES = (
        (PAPER_BASED, "Paper-Based"),
        (ONLINE, "Online"),
        (HYBRID, "Hybrid"),
    )

    name = models.CharField(max_length=128)
    term = models.ForeignKey("academics.AcademicTerm", on_delete=models.CASCADE)
    exam_mode = models.CharField(max_length=16, choices=EXAM_MODE_CHOICES, default=PAPER_BASED)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True, help_text="General instructions for all papers in this exam")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-term__year__name", "term__order", "name")
        unique_together = ("term", "name")

    def __str__(self) -> str:
        return f"{self.term} - {self.name}"

    def total_papers(self):
        return self.papers.count()

    def published_papers(self):
        return self.papers.filter(is_published=True).count()


class ExamPaper(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="papers")
    offering = models.ForeignKey("academics.CourseOffering", on_delete=models.CASCADE)
    max_score = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    passing_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    weight = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True, help_text="Duration for online exams")
    is_published = models.BooleanField(default=False)
    results_published = models.BooleanField(default=False, help_text="Allow students and parents to view final results.")
    results_published_at = models.DateTimeField(null=True, blank=True)
    report_cards_enabled = models.BooleanField(default=True)
    date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    instructions = models.TextField(blank=True)
    allow_calculator = models.BooleanField(default=False)
    randomize_questions = models.BooleanField(default=False, help_text="Randomize question order for online exams")
    show_results_immediately = models.BooleanField(default=False, help_text="Show results after submission")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        unique_together = ("exam", "offering")

    def __str__(self) -> str:
        return f"{self.exam} - {self.offering}"

    def total_questions(self):
        return self.questions.count()

    def total_marks(self):
        return self.questions.aggregate(total=models.Sum("marks"))["total"] or 0

    def average_score(self):
        scores = self.scores.filter(score__isnull=False)
        if scores.exists():
            return scores.aggregate(avg=models.Avg("score"))["avg"]
        return None

    def pass_rate(self):
        if not self.passing_score:
            return None
        total = self.scores.filter(score__isnull=False).count()
        if total == 0:
            return 0
        passed = self.scores.filter(score__gte=self.passing_score).count()
        return (passed / total) * 100

    def results_are_visible(self):
        return self.results_published or self.show_results_immediately


class QuestionBank(models.Model):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"

    DIFFICULTY_CHOICES = (
        (EASY, "Easy"),
        (MEDIUM, "Medium"),
        (HARD, "Hard"),
    )

    MCQ = "MCQ"
    TRUE_FALSE = "TRUE_FALSE"
    SHORT_ANSWER = "SHORT_ANSWER"
    ESSAY = "ESSAY"
    FILL_BLANK = "FILL_BLANK"

    QUESTION_TYPE_CHOICES = (
        (MCQ, "Multiple Choice"),
        (TRUE_FALSE, "True/False"),
        (SHORT_ANSWER, "Short Answer"),
        (ESSAY, "Essay"),
        (FILL_BLANK, "Fill in the Blank"),
    )

    course = models.ForeignKey("academics.Course", on_delete=models.CASCADE, related_name="questions")
    question_type = models.CharField(max_length=16, choices=QUESTION_TYPE_CHOICES)
    difficulty = models.CharField(max_length=16, choices=DIFFICULTY_CHOICES, default=MEDIUM)
    question_text = models.TextField()
    question_image = models.ImageField(upload_to="exam_questions/", null=True, blank=True)
    marks = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    option_a = models.CharField(max_length=255, blank=True)
    option_b = models.CharField(max_length=255, blank=True)
    option_c = models.CharField(max_length=255, blank=True)
    option_d = models.CharField(max_length=255, blank=True)
    correct_option = models.CharField(max_length=1, blank=True, help_text="A, B, C, or D")
    correct_answer = models.TextField(blank=True)
    explanation = models.TextField(blank=True, help_text="Explanation for the correct answer")
    tags = models.CharField(max_length=255, blank=True, help_text="Comma-separated tags")
    created_by = models.ForeignKey("teachers.TeacherProfile", on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.get_question_type_display()} - {self.question_text[:50]}"

    def is_objective(self):
        return self.question_type in [self.MCQ, self.TRUE_FALSE, self.FILL_BLANK]


class ExamQuestion(models.Model):
    paper = models.ForeignKey(ExamPaper, on_delete=models.CASCADE, related_name="questions")
    question = models.ForeignKey(QuestionBank, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=1)
    marks = models.DecimalField(max_digits=5, decimal_places=2, help_text="Marks for this question in this exam")

    class Meta:
        ordering = ("paper", "order")
        unique_together = ("paper", "question")

    def __str__(self) -> str:
        return f"{self.paper} - Q{self.order}"


class ExamSchedule(models.Model):
    paper = models.ForeignKey(ExamPaper, on_delete=models.CASCADE, related_name="schedules")
    room_name = models.CharField(max_length=128)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    capacity = models.PositiveIntegerField()
    invigilator = models.ForeignKey("teachers.TeacherProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="invigilated_exams")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("date", "start_time")

    def __str__(self) -> str:
        return f"{self.paper} - {self.room_name} ({self.date})"

    def allocated_seats(self):
        return self.seat_allocations.count()

    def available_seats(self):
        return self.capacity - self.allocated_seats()


class SeatAllocation(models.Model):
    schedule = models.ForeignKey(ExamSchedule, on_delete=models.CASCADE, related_name="seat_allocations")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    seat_number = models.CharField(max_length=16)
    admit_card_generated = models.BooleanField(default=False)
    admit_card_generated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("seat_number",)
        unique_together = ("schedule", "student")

    def __str__(self) -> str:
        return f"{self.student} - Seat {self.seat_number}"


class OnlineExamAttempt(models.Model):
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    AUTO_SUBMITTED = "AUTO_SUBMITTED"
    GRADED = "GRADED"

    STATUS_CHOICES = (
        (IN_PROGRESS, "In Progress"),
        (SUBMITTED, "Submitted"),
        (AUTO_SUBMITTED, "Auto-Submitted"),
        (GRADED, "Graded"),
    )

    paper = models.ForeignKey(ExamPaper, on_delete=models.CASCADE, related_name="attempts")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="exam_attempts")
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=IN_PROGRESS)
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    submitted_by_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_fingerprint = models.CharField(max_length=255, blank=True)
    question_order = models.JSONField(default=list, blank=True)
    browser_focus_warnings = models.PositiveIntegerField(default=0)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("-started_at",)
        unique_together = ("paper", "student")

    def __str__(self) -> str:
        return f"{self.student} - {self.paper} ({self.status})"

    def time_remaining(self):
        if self.status != self.IN_PROGRESS or not self.paper.duration_minutes:
            return None
        elapsed = timezone.now() - self.started_at
        total_seconds = self.paper.duration_minutes * 60
        remaining = total_seconds - elapsed.total_seconds()
        return max(0, remaining)

    def is_expired(self):
        remaining = self.time_remaining()
        return remaining == 0 if remaining is not None else False

    def is_locked(self):
        return self.status in [self.SUBMITTED, self.AUTO_SUBMITTED, self.GRADED] or self.locked_at is not None


class StudentResponse(models.Model):
    attempt = models.ForeignKey(OnlineExamAttempt, on_delete=models.CASCADE, related_name="responses")
    exam_question = models.ForeignKey(ExamQuestion, on_delete=models.CASCADE)
    selected_option = models.CharField(max_length=1, blank=True, help_text="A, B, C, or D for MCQ")
    answer_text = models.TextField(blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    marks_awarded = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    manual_feedback = models.TextField(blank=True)
    manually_marked_by = models.ForeignKey("teachers.TeacherProfile", on_delete=models.SET_NULL, null=True, blank=True)
    manually_marked_at = models.DateTimeField(null=True, blank=True)
    answered_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("exam_question__order",)
        unique_together = ("attempt", "exam_question")

    def __str__(self) -> str:
        return f"{self.attempt.student} - Q{self.exam_question.order}"

    def auto_grade(self):
        question = self.exam_question.question
        if question.question_type in [QuestionBank.MCQ, QuestionBank.TRUE_FALSE]:
            if self.selected_option.upper() == question.correct_option.upper():
                self.is_correct = True
                self.marks_awarded = self.exam_question.marks
            else:
                self.is_correct = False
                self.marks_awarded = Decimal(0)
            self.save()
            return True
        if question.question_type == QuestionBank.FILL_BLANK:
            if self.answer_text.strip().lower() == question.correct_answer.strip().lower():
                self.is_correct = True
                self.marks_awarded = self.exam_question.marks
            else:
                self.is_correct = False
                self.marks_awarded = Decimal(0)
            self.save()
            return True
        return False


class ExamAntiCheatEvent(models.Model):
    FOCUS_LOST = "FOCUS_LOST"
    TAB_HIDDEN = "TAB_HIDDEN"
    COPY_PASTE = "COPY_PASTE"
    FULLSCREEN_EXIT = "FULLSCREEN_EXIT"
    AUTO_SUBMIT = "AUTO_SUBMIT"
    START = "START"
    SAVE = "SAVE"
    SUBMIT = "SUBMIT"
    MANUAL_REVIEW = "MANUAL_REVIEW"

    EVENT_CHOICES = (
        (FOCUS_LOST, "Focus lost"),
        (TAB_HIDDEN, "Tab hidden"),
        (COPY_PASTE, "Copy/paste attempt"),
        (FULLSCREEN_EXIT, "Fullscreen exit"),
        (AUTO_SUBMIT, "Auto submit"),
        (START, "Attempt started"),
        (SAVE, "Answers saved"),
        (SUBMIT, "Attempt submitted"),
        (MANUAL_REVIEW, "Manual review"),
    )

    attempt = models.ForeignKey(OnlineExamAttempt, on_delete=models.CASCADE, related_name="security_events")
    event_type = models.CharField(max_length=32, choices=EVENT_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["attempt", "event_type", "created_at"])]

    def __str__(self) -> str:
        return f"{self.attempt} - {self.event_type}"


class ExamScore(models.Model):
    paper = models.ForeignKey(ExamPaper, on_delete=models.CASCADE, related_name="scores")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    grade = models.CharField(max_length=8, blank=True)
    rank = models.PositiveIntegerField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    graded_by = models.ForeignKey("teachers.TeacherProfile", on_delete=models.SET_NULL, null=True, blank=True)
    graded_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("student__last_name", "student__first_name")
        unique_together = ("paper", "student")

    def __str__(self) -> str:
        return f"{self.student} -> {self.paper}"

    def calculate_percentage(self):
        if self.score is not None and self.paper.max_score:
            self.percentage = (self.score / self.paper.max_score) * 100
            self.save()

    def is_pass(self):
        if self.paper.passing_score and self.score is not None:
            return self.score >= self.paper.passing_score
        return None


class ExamAnalytics(models.Model):
    paper = models.OneToOneField(ExamPaper, on_delete=models.CASCADE, related_name="analytics")
    total_students = models.PositiveIntegerField(default=0)
    appeared_students = models.PositiveIntegerField(default=0)
    passed_students = models.PositiveIntegerField(default=0)
    failed_students = models.PositiveIntegerField(default=0)
    average_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    highest_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    lowest_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    median_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    pass_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Exam Analytics"

    def __str__(self) -> str:
        return f"Analytics - {self.paper}"

    def refresh_analytics(self):
        from django.db.models import Avg, Max, Min
        scores = self.paper.scores.filter(score__isnull=False)
        self.total_students = self.paper.scores.count()
        self.appeared_students = scores.count()
        if scores.exists():
            stats = scores.aggregate(avg=Avg("score"), max=Max("score"), min=Min("score"))
            self.average_score = stats["avg"]
            self.highest_score = stats["max"]
            self.lowest_score = stats["min"]
            if self.paper.passing_score:
                self.passed_students = scores.filter(score__gte=self.paper.passing_score).count()
                self.failed_students = self.appeared_students - self.passed_students
                self.pass_rate = (self.passed_students / self.appeared_students * 100) if self.appeared_students > 0 else 0
        self.save()
