# Generated initial migration for quizzes app

import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('orgsettings', '0002_statushistory_notification_actionlog'),
        ('academics', '0002_campus_scoping'),
        ('students', '0002_studentprofile_campus'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Quiz',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('name', models.CharField(help_text='Quiz title', max_length=200)),
                ('topic', models.CharField(blank=True, help_text='Quiz topic/subject', max_length=200)),
                ('description', models.TextField(blank=True)),
                ('time_limit_minutes', models.IntegerField(default=60, help_text='Time limit in minutes')),
                ('show_one_question_at_time', models.BooleanField(default=False, help_text='Show questions on separate pages')),
                ('passing_score_percentage', models.IntegerField(blank=True, help_text='Minimum percentage to pass (0-100)', null=True)),
                ('difficulty', models.CharField(choices=[('EASY', 'Easy'), ('MEDIUM', 'Medium'), ('HARD', 'Hard')], default='MEDIUM', max_length=10)),
                ('is_active', models.BooleanField(default=False, help_text='Quiz is available to students')),
                ('available_from', models.DateTimeField(blank=True, null=True)),
                ('available_until', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('campus', models.ForeignKey(blank=True, help_text='Campus this quiz belongs to', null=True, on_delete=django.db.models.deletion.CASCADE, to='orgsettings.campus')),
                ('course_offering', models.ForeignKey(help_text='Course offering this quiz is for', on_delete=django.db.models.deletion.CASCADE, related_name='quizzes', to='academics.courseoffering')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_quizzes', to=settings.AUTH_USER_MODEL)),
                ('students', models.ManyToManyField(blank=True, help_text='Specific students assigned to this quiz (leave empty for all in course)', related_name='assigned_quizzes', to='students.studentprofile')),
            ],
            options={
                'verbose_name': 'Quiz',
                'verbose_name_plural': 'Quizzes',
                'ordering': ('-created_at',),
            },
        ),
        migrations.CreateModel(
            name='QuizQuestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question_text', models.TextField(help_text='Question text')),
                ('question_type', models.CharField(choices=[('MULTIPLE_CHOICE', 'Multiple Choice'), ('TRUE_FALSE', 'True/False'), ('SHORT_ANSWER', 'Short Answer'), ('ESSAY', 'Essay')], default='MULTIPLE_CHOICE', max_length=20)),
                ('points', models.DecimalField(decimal_places=2, default=1.0, help_text='Points for this question', max_digits=5)),
                ('order', models.PositiveIntegerField(default=0, help_text='Display order')),
                ('correct_answer', models.TextField(blank=True, help_text='Correct answer (for reference, not auto-graded for essay questions)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('quiz', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questions', to='quizzes.quiz')),
            ],
            options={
                'verbose_name': 'Quiz Question',
                'verbose_name_plural': 'Quiz Questions',
                'ordering': ('quiz', 'order', 'id'),
            },
        ),
        migrations.CreateModel(
            name='QuizQuestionChoice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('choice_text', models.CharField(max_length=500)),
                ('is_correct', models.BooleanField(default=False)),
                ('order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='choices', to='quizzes.quizquestion')),
            ],
            options={
                'verbose_name': 'Question Choice',
                'verbose_name_plural': 'Question Choices',
                'ordering': ('question', 'order', 'id'),
            },
        ),
        migrations.CreateModel(
            name='QuizAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('IN_PROGRESS', 'In Progress'), ('COMPLETED', 'Completed'), ('GRADED', 'Graded')], default='IN_PROGRESS', max_length=20)),
                ('started_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('score', models.DecimalField(blank=True, decimal_places=2, help_text='Total score achieved', max_digits=5, null=True)),
                ('max_score', models.DecimalField(blank=True, decimal_places=2, help_text='Maximum possible score', max_digits=5, null=True)),
                ('percentage', models.DecimalField(blank=True, decimal_places=2, help_text='Score as percentage', max_digits=5, null=True)),
                ('passed', models.BooleanField(blank=True, null=True)),
                ('graded_at', models.DateTimeField(blank=True, null=True)),
                ('feedback', models.TextField(blank=True)),
                ('graded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='graded_quiz_attempts', to=settings.AUTH_USER_MODEL)),
                ('quiz', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attempts', to='quizzes.quiz')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='quiz_attempts', to='students.studentprofile')),
            ],
            options={
                'verbose_name': 'Quiz Attempt',
                'verbose_name_plural': 'Quiz Attempts',
                'ordering': ('-started_at',),
            },
        ),
        migrations.CreateModel(
            name='QuizAnswer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('answer_text', models.TextField(blank=True)),
                ('is_correct', models.BooleanField(blank=True, null=True)),
                ('points_earned', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('feedback', models.TextField(blank=True)),
                ('answered_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('attempt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='answers', to='quizzes.quizattempt')),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='quizzes.quizquestion')),
                ('selected_choice', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='quizzes.quizquestionchoice')),
            ],
            options={
                'verbose_name': 'Quiz Answer',
                'verbose_name_plural': 'Quiz Answers',
            },
        ),
        migrations.AddConstraint(
            model_name='quizattempt',
            constraint=models.UniqueConstraint(fields=('quiz', 'student'), name='unique_quiz_attempt_per_student'),
        ),
        migrations.AddConstraint(
            model_name='quizanswer',
            constraint=models.UniqueConstraint(fields=('attempt', 'question'), name='unique_answer_per_question'),
        ),
    ]
