# Generated initial migration for polls app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('orgsettings', '0002_statushistory_notification_actionlog'),
        ('students', '0002_studentprofile_campus'),
        ('teachers', '0002_teacherprofile_campus'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Poll',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(help_text='Poll question or title', max_length=200)),
                ('description', models.TextField(blank=True, help_text='Additional details about the poll')),
                ('audience', models.CharField(choices=[('ALL', 'All Users'), ('ADMIN', 'Administrators'), ('TEACHERS', 'Teachers'), ('STUDENTS', 'Students'), ('PARENTS', 'Parents'), ('STAFF', 'Staff')], default='ALL', help_text='Target audience for this poll', max_length=20)),
                ('is_active', models.BooleanField(default=False, help_text='Poll is visible and accepting responses')),
                ('is_anonymous', models.BooleanField(default=False, help_text='Responses are anonymous')),
                ('allow_multiple_votes', models.BooleanField(default=False, help_text='Users can change their vote')),
                ('show_results_before_voting', models.BooleanField(default=False, help_text='Show results before user votes')),
                ('available_from', models.DateTimeField(blank=True, null=True)),
                ('available_until', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('campus', models.ForeignKey(blank=True, help_text='Campus this poll is for (leave empty for all campuses)', null=True, on_delete=django.db.models.deletion.CASCADE, to='orgsettings.campus')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_polls', to=settings.AUTH_USER_MODEL)),
                ('specific_students', models.ManyToManyField(blank=True, help_text='Specific students to poll (leave empty for all students if audience=STUDENTS)', related_name='assigned_polls', to='students.studentprofile')),
                ('specific_teachers', models.ManyToManyField(blank=True, help_text='Specific teachers to poll', related_name='assigned_polls', to='teachers.teacherprofile')),
            ],
            options={
                'verbose_name': 'Poll',
                'verbose_name_plural': 'Polls & Surveys',
                'ordering': ('-created_at',),
            },
        ),
        migrations.CreateModel(
            name='PollOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('option_text', models.CharField(help_text='Option text', max_length=200)),
                ('order', models.PositiveIntegerField(default=0, help_text='Display order')),
                ('vote_count', models.PositiveIntegerField(default=0, help_text='Number of votes')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('poll', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='options', to='polls.poll')),
            ],
            options={
                'verbose_name': 'Poll Option',
                'verbose_name_plural': 'Poll Options',
                'ordering': ('poll', 'order', 'id'),
            },
        ),
        migrations.CreateModel(
            name='PollVote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.CharField(blank=True, max_length=255)),
                ('voted_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('option', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='votes', to='polls.polloption')),
                ('poll', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='votes', to='polls.poll')),
                ('user', models.ForeignKey(blank=True, help_text='User who voted (null for anonymous polls)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='poll_votes', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Poll Vote',
                'verbose_name_plural': 'Poll Votes',
                'ordering': ('-voted_at',),
            },
        ),
    ]
