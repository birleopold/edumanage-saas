"""
Quiz and Assessment models - Adapted from PicoSchool
Enhanced for multi-campus support and integration with existing system
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Quiz(models.Model):
    """
    Main Quiz model for creating assessments.
    """
    EASY = 'EASY'
    MEDIUM = 'MEDIUM'
    HARD = 'HARD'
    
    DIFFICULTY_CHOICES = (
        (EASY, 'Easy'),
        (MEDIUM, 'Medium'),
        (HARD, 'Hard'),
    )
    
    # Identification
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=200, help_text='Quiz title')
    topic = models.CharField(max_length=200, blank=True, help_text='Quiz topic/subject')
    description = models.TextField(blank=True)
    
    # Relations
    campus = models.ForeignKey(
        'orgsettings.Campus',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text='Campus this quiz belongs to'
    )
    course_offering = models.ForeignKey(
        'academics.CourseOffering',
        on_delete=models.CASCADE,
        related_name='quizzes',
        help_text='Course offering this quiz is for'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_quizzes'
    )
    
    # Quiz settings
    time_limit_minutes = models.IntegerField(
        help_text='Time limit in minutes',
        default=60
    )
    show_one_question_at_time = models.BooleanField(
        default=False,
        help_text='Show questions on separate pages'
    )
    passing_score_percentage = models.IntegerField(
        null=True,
        blank=True,
        help_text='Minimum percentage to pass (0-100)'
    )
    difficulty = models.CharField(
        max_length=10,
        choices=DIFFICULTY_CHOICES,
        default=MEDIUM
    )
    
    # Availability
    is_active = models.BooleanField(default=False, help_text='Quiz is available to students')
    available_from = models.DateTimeField(null=True, blank=True)
    available_until = models.DateTimeField(null=True, blank=True)
    
    # Students who can take this quiz
    students = models.ManyToManyField(
        'students.StudentProfile',
        related_name='assigned_quizzes',
        blank=True,
        help_text='Specific students assigned to this quiz (leave empty for all in course)'
    )
    
    # Metadata
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Quiz'
        verbose_name_plural = 'Quizzes'
        ordering = ('-created_at',)
    
    def __str__(self):
        return f"{self.name} - {self.course_offering}"
    
    def get_questions(self):
        """Get all questions for this quiz."""
        return self.questions.all()
    
    def get_question_count(self):
        """Get total number of questions."""
        return self.questions.count()
    
    def is_available(self):
        """Check if quiz is currently available."""
        if not self.is_active:
            return False
        now = timezone.now()
        if self.available_from and now < self.available_from:
            return False
        if self.available_until and now > self.available_until:
            return False
        return True


class QuizQuestion(models.Model):
    """
    Individual question in a quiz.
    """
    MULTIPLE_CHOICE = 'MULTIPLE_CHOICE'
    TRUE_FALSE = 'TRUE_FALSE'
    SHORT_ANSWER = 'SHORT_ANSWER'
    ESSAY = 'ESSAY'
    
    QUESTION_TYPE_CHOICES = (
        (MULTIPLE_CHOICE, 'Multiple Choice'),
        (TRUE_FALSE, 'True/False'),
        (SHORT_ANSWER, 'Short Answer'),
        (ESSAY, 'Essay'),
    )
    
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    question_text = models.TextField(help_text='Question text')
    question_type = models.CharField(
        max_length=20,
        choices=QUESTION_TYPE_CHOICES,
        default=MULTIPLE_CHOICE
    )
    points = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1.0,
        help_text='Points for this question'
    )
    order = models.PositiveIntegerField(default=0, help_text='Display order')
    
    # For essay/short answer questions
    correct_answer = models.TextField(
        blank=True,
        help_text='Correct answer (for reference, not auto-graded for essay questions)'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Quiz Question'
        verbose_name_plural = 'Quiz Questions'
        ordering = ('quiz', 'order', 'id')
    
    def __str__(self):
        return f"Q{self.order}: {self.question_text[:50]}"
    
    def get_choices(self):
        """Get all answer choices for multiple choice questions."""
        return self.choices.all()


class QuizQuestionChoice(models.Model):
    """
    Answer choices for multiple choice questions.
    """
    question = models.ForeignKey(
        QuizQuestion,
        on_delete=models.CASCADE,
        related_name='choices'
    )
    choice_text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Question Choice'
        verbose_name_plural = 'Question Choices'
        ordering = ('question', 'order', 'id')
    
    def __str__(self):
        return f"{self.choice_text} ({'Correct' if self.is_correct else 'Incorrect'})"


class QuizAttempt(models.Model):
    """
    Student's attempt at taking a quiz.
    """
    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETED = 'COMPLETED'
    GRADED = 'GRADED'
    
    STATUS_CHOICES = (
        (IN_PROGRESS, 'In Progress'),
        (COMPLETED, 'Completed'),
        (GRADED, 'Graded'),
    )
    
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='attempts'
    )
    student = models.ForeignKey(
        'students.StudentProfile',
        on_delete=models.CASCADE,
        related_name='quiz_attempts'
    )
    
    # Attempt details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=IN_PROGRESS)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Scoring
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Total score achieved'
    )
    max_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Maximum possible score'
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Score as percentage'
    )
    passed = models.BooleanField(null=True, blank=True)
    
    # Grading
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='graded_quiz_attempts'
    )
    graded_at = models.DateTimeField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Quiz Attempt'
        verbose_name_plural = 'Quiz Attempts'
        ordering = ('-started_at',)
        unique_together = ('quiz', 'student')  # One attempt per student per quiz
    
    def __str__(self):
        return f"{self.student} - {self.quiz.name} ({self.status})"
    
    def calculate_score(self):
        """Calculate total score from answers."""
        total_score = 0
        max_possible = 0
        
        for answer in self.answers.all():
            max_possible += float(answer.question.points)
            if answer.is_correct:
                total_score += float(answer.points_earned or 0)
        
        self.score = total_score
        self.max_score = max_possible
        
        if max_possible > 0:
            self.percentage = (total_score / max_possible) * 100
            if self.quiz.passing_score_percentage:
                self.passed = self.percentage >= self.quiz.passing_score_percentage
        
        self.save()
        return self.score


class QuizAnswer(models.Model):
    """
    Student's answer to a quiz question.
    """
    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    question = models.ForeignKey(
        QuizQuestion,
        on_delete=models.CASCADE
    )
    
    # For multiple choice
    selected_choice = models.ForeignKey(
        QuizQuestionChoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # For text answers
    answer_text = models.TextField(blank=True)
    
    # Grading
    is_correct = models.BooleanField(null=True, blank=True)
    points_earned = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    feedback = models.TextField(blank=True)
    
    answered_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        verbose_name = 'Quiz Answer'
        verbose_name_plural = 'Quiz Answers'
        unique_together = ('attempt', 'question')
    
    def __str__(self):
        return f"{self.attempt.student} - Q{self.question.order}"
    
    def auto_grade(self):
        """Auto-grade multiple choice and true/false questions."""
        if self.question.question_type == QuizQuestion.MULTIPLE_CHOICE:
            if self.selected_choice and self.selected_choice.is_correct:
                self.is_correct = True
                self.points_earned = self.question.points
            else:
                self.is_correct = False
                self.points_earned = 0
            self.save()
        elif self.question.question_type == QuizQuestion.TRUE_FALSE:
            if self.answer_text.lower() == self.question.correct_answer.lower():
                self.is_correct = True
                self.points_earned = self.question.points
            else:
                self.is_correct = False
                self.points_earned = 0
            self.save()
