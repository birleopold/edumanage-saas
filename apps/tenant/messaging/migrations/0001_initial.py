# Generated initial migration for messaging app

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
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Conversation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('subject', models.CharField(help_text='Conversation subject', max_length=200)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_archived', models.BooleanField(default=False)),
                ('campus', models.ForeignKey(blank=True, help_text='Campus context for this conversation', null=True, on_delete=django.db.models.deletion.SET_NULL, to='orgsettings.campus')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='started_conversations', to=settings.AUTH_USER_MODEL)),
                ('participants', models.ManyToManyField(help_text='Users in this conversation', related_name='conversations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Conversation',
                'verbose_name_plural': 'Conversations',
                'ordering': ('-updated_at',),
            },
        ),
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField(help_text='Message content')),
                ('attachment', models.FileField(blank=True, null=True, upload_to='messaging/attachments/%Y/%m/')),
                ('sent_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('edited_at', models.DateTimeField(blank=True, null=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('conversation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='messaging.conversation')),
                ('read_by', models.ManyToManyField(blank=True, related_name='read_messages', to=settings.AUTH_USER_MODEL)),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_messages', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Message',
                'verbose_name_plural': 'Messages',
                'ordering': ('-sent_at',),
            },
        ),
        migrations.CreateModel(
            name='Announcement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('title', models.CharField(max_length=200)),
                ('content', models.TextField()),
                ('scope', models.CharField(choices=[('SYSTEM', 'System-wide'), ('CAMPUS', 'Campus-wide'), ('CLASS', 'Class-specific')], default='CAMPUS', max_length=20)),
                ('audience', models.CharField(choices=[('ALL', 'All Users'), ('TEACHERS', 'Teachers'), ('STUDENTS', 'Students'), ('PARENTS', 'Parents'), ('STAFF', 'Staff')], default='ALL', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('is_urgent', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('campus', models.ForeignKey(blank=True, help_text='Campus for campus-wide announcements', null=True, on_delete=django.db.models.deletion.CASCADE, to='orgsettings.campus')),
                ('class_group', models.ForeignKey(blank=True, help_text='Class for class-specific announcements', null=True, on_delete=django.db.models.deletion.CASCADE, to='academics.classgroup')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_announcements_msg', to=settings.AUTH_USER_MODEL)),
                ('read_by', models.ManyToManyField(blank=True, related_name='read_announcements_msg', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Announcement',
                'verbose_name_plural': 'Announcements',
                'ordering': ('-created_at',),
            },
        ),
    ]
