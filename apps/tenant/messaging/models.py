"""
Internal messaging system - Adapted from StudX
Enhanced for multi-campus support and role-based messaging
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Conversation(models.Model):
    """
    Conversation thread between users.
    """
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    subject = models.CharField(max_length=200, help_text='Conversation subject')
    
    # Participants
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='conversations',
        help_text='Users in this conversation'
    )
    
    # Campus context (optional)
    campus = models.ForeignKey(
        'orgsettings.Campus',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Campus context for this conversation'
    )
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='started_conversations'
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Status
    is_archived = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Conversation'
        verbose_name_plural = 'Conversations'
        ordering = ('-updated_at',)
    
    def __str__(self):
        return f"{self.subject} ({self.participants.count()} participants)"
    
    def get_last_message(self):
        """Get the most recent message in this conversation."""
        return self.messages.first()
    
    def get_unread_count(self, user):
        """Get count of unread messages for a specific user."""
        return self.messages.exclude(read_by=user).count()
    
    def mark_as_read(self, user):
        """Mark all messages as read for a user."""
        unread_messages = self.messages.exclude(read_by=user)
        for message in unread_messages:
            message.read_by.add(user)


class Message(models.Model):
    """
    Individual message in a conversation.
    """
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    
    # Content
    content = models.TextField(help_text='Message content')
    
    # Attachments (optional)
    attachment = models.FileField(
        upload_to='messaging/attachments/%Y/%m/',
        null=True,
        blank=True
    )
    
    # Read tracking
    read_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='read_messages',
        blank=True
    )
    
    # Metadata
    sent_at = models.DateTimeField(default=timezone.now)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
        ordering = ('-sent_at',)
    
    def __str__(self):
        return f"{self.sender.username}: {self.content[:50]}"
    
    def is_read_by(self, user):
        """Check if message has been read by a user."""
        return self.read_by.filter(pk=user.pk).exists()
    
    def mark_as_read(self, user):
        """Mark message as read by a user."""
        if not self.is_read_by(user):
            self.read_by.add(user)


class Announcement(models.Model):
    """
    System-wide or campus-wide announcements (one-way communication).
    Different from apps.tenant.announcements - this is for internal messaging.
    """
    SYSTEM = 'SYSTEM'
    CAMPUS = 'CAMPUS'
    CLASS = 'CLASS'
    
    SCOPE_CHOICES = (
        (SYSTEM, 'System-wide'),
        (CAMPUS, 'Campus-wide'),
        (CLASS, 'Class-specific'),
    )
    
    ALL = 'ALL'
    TEACHERS = 'TEACHERS'
    STUDENTS = 'STUDENTS'
    PARENTS = 'PARENTS'
    STAFF = 'STAFF'
    
    AUDIENCE_CHOICES = (
        (ALL, 'All Users'),
        (TEACHERS, 'Teachers'),
        (STUDENTS, 'Students'),
        (PARENTS, 'Parents'),
        (STAFF, 'Staff'),
    )
    
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    title = models.CharField(max_length=200)
    content = models.TextField()
    
    # Scope
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default=CAMPUS)
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default=ALL)
    
    # Relations
    campus = models.ForeignKey(
        'orgsettings.Campus',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text='Campus for campus-wide announcements'
    )
    class_group = models.ForeignKey(
        'academics.ClassGroup',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text='Class for class-specific announcements'
    )
    
    # Creator
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_announcements_msg'
    )
    
    # Settings
    is_active = models.BooleanField(default=True)
    is_urgent = models.BooleanField(default=False)
    
    # Tracking
    read_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='read_announcements_msg',
        blank=True
    )
    
    # Metadata
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Announcement'
        verbose_name_plural = 'Announcements'
        ordering = ('-created_at',)
    
    def __str__(self):
        return self.title
    
    def is_expired(self):
        """Check if announcement has expired."""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def get_read_count(self):
        """Get number of users who have read this announcement."""
        return self.read_by.count()
