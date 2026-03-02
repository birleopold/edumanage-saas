"""
Poll and Survey models - Adapted from PicoSchool
Enhanced for multi-campus support and role-based targeting
"""
from django.conf import settings
from django.db import models
from django.db.models import Count, Sum
from django.utils import timezone


class Poll(models.Model):
    """
    Poll/Survey model for gathering feedback and opinions.
    """
    ALL = 'ALL'
    ADMIN = 'ADMIN'
    TEACHERS = 'TEACHERS'
    STUDENTS = 'STUDENTS'
    PARENTS = 'PARENTS'
    STAFF = 'STAFF'
    
    AUDIENCE_CHOICES = (
        (ALL, 'All Users'),
        (ADMIN, 'Administrators'),
        (TEACHERS, 'Teachers'),
        (STUDENTS, 'Students'),
        (PARENTS, 'Parents'),
        (STAFF, 'Staff'),
    )
    
    # Basic info
    title = models.CharField(max_length=200, help_text='Poll question or title')
    description = models.TextField(blank=True, help_text='Additional details about the poll')
    
    # Relations
    campus = models.ForeignKey(
        'orgsettings.Campus',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text='Campus this poll is for (leave empty for all campuses)'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_polls'
    )
    
    # Targeting
    audience = models.CharField(
        max_length=20,
        choices=AUDIENCE_CHOICES,
        default=ALL,
        help_text='Target audience for this poll'
    )
    
    # Specific users (optional - for targeted polls)
    specific_students = models.ManyToManyField(
        'students.StudentProfile',
        related_name='assigned_polls',
        blank=True,
        help_text='Specific students to poll (leave empty for all students if audience=STUDENTS)'
    )
    specific_teachers = models.ManyToManyField(
        'teachers.TeacherProfile',
        related_name='assigned_polls',
        blank=True,
        help_text='Specific teachers to poll'
    )
    
    # Settings
    is_active = models.BooleanField(default=False, help_text='Poll is visible and accepting responses')
    is_anonymous = models.BooleanField(default=False, help_text='Responses are anonymous')
    allow_multiple_votes = models.BooleanField(default=False, help_text='Users can change their vote')
    show_results_before_voting = models.BooleanField(default=False, help_text='Show results before user votes')
    
    # Availability
    available_from = models.DateTimeField(null=True, blank=True)
    available_until = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Poll'
        verbose_name_plural = 'Polls & Surveys'
        ordering = ('-created_at',)
    
    def __str__(self):
        return self.title
    
    def get_total_votes(self):
        """Get total number of votes across all options."""
        return self.options.aggregate(total=Sum('vote_count'))['total'] or 0
    
    def get_total_voters(self):
        """Get number of unique voters."""
        return self.votes.values('user').distinct().count()
    
    def is_available(self):
        """Check if poll is currently available."""
        if not self.is_active:
            return False
        now = timezone.now()
        if self.available_from and now < self.available_from:
            return False
        if self.available_until and now > self.available_until:
            return False
        return True
    
    def has_user_voted(self, user):
        """Check if a user has already voted."""
        return self.votes.filter(user=user).exists()
    
    def get_results(self):
        """Get poll results with percentages."""
        total_votes = self.get_total_votes()
        results = []
        
        for option in self.options.all():
            percentage = (option.vote_count / total_votes * 100) if total_votes > 0 else 0
            results.append({
                'option': option,
                'votes': option.vote_count,
                'percentage': round(percentage, 1)
            })
        
        return results


class PollOption(models.Model):
    """
    Individual option/choice in a poll.
    """
    poll = models.ForeignKey(
        Poll,
        on_delete=models.CASCADE,
        related_name='options'
    )
    option_text = models.CharField(max_length=200, help_text='Option text')
    order = models.PositiveIntegerField(default=0, help_text='Display order')
    vote_count = models.PositiveIntegerField(default=0, help_text='Number of votes')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Poll Option'
        verbose_name_plural = 'Poll Options'
        ordering = ('poll', 'order', 'id')
    
    def __str__(self):
        return f"{self.option_text} ({self.vote_count} votes)"
    
    def get_percentage(self):
        """Get percentage of total votes."""
        total = self.poll.get_total_votes()
        if total == 0:
            return 0
        return round((self.vote_count / total) * 100, 1)


class PollVote(models.Model):
    """
    Record of a user's vote on a poll.
    """
    poll = models.ForeignKey(
        Poll,
        on_delete=models.CASCADE,
        related_name='votes'
    )
    option = models.ForeignKey(
        PollOption,
        on_delete=models.CASCADE,
        related_name='votes'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='poll_votes',
        null=True,
        blank=True,
        help_text='User who voted (null for anonymous polls)'
    )
    
    # For tracking even in anonymous polls
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    
    voted_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        verbose_name = 'Poll Vote'
        verbose_name_plural = 'Poll Votes'
        ordering = ('-voted_at',)
    
    def __str__(self):
        user_display = self.user.username if self.user else 'Anonymous'
        return f"{user_display} voted for {self.option.option_text}"
    
    def save(self, *args, **kwargs):
        """Update vote count when saving."""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            # Increment vote count
            self.option.vote_count += 1
            self.option.save(update_fields=['vote_count'])
    
    def delete(self, *args, **kwargs):
        """Update vote count when deleting."""
        option = self.option
        super().delete(*args, **kwargs)
        
        # Decrement vote count
        if option.vote_count > 0:
            option.vote_count -= 1
            option.save(update_fields=['vote_count'])
