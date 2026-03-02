"""
Utility functions for audit trail and notifications.
"""
from django.contrib.contenttypes.models import ContentType

from .models import ActionLog, Notification, StatusHistory


def log_status_change(instance, old_status, new_status, user=None, reason=''):
    """
    Log a status change for any model instance.
    
    Args:
        instance: Model instance that changed status
        old_status: Previous status value
        new_status: New status value
        user: User who made the change
        reason: Optional reason for the change
    
    Returns:
        StatusHistory instance
    """
    content_type = ContentType.objects.get_for_model(instance)
    
    return StatusHistory.objects.create(
        content_type=content_type,
        object_id=instance.pk,
        old_status=old_status,
        new_status=new_status,
        changed_by=user,
        reason=reason
    )


def log_action(instance, action, description='', user=None, metadata=None):
    """
    Log an action performed on any model instance.
    
    Args:
        instance: Model instance the action was performed on
        action: Short action name (e.g., "Payment Received")
        description: Detailed description
        user: User who performed the action
        metadata: Optional dict of additional data
    
    Returns:
        ActionLog instance
    """
    content_type = ContentType.objects.get_for_model(instance)
    
    return ActionLog.objects.create(
        content_type=content_type,
        object_id=instance.pk,
        action=action,
        description=description,
        performed_by=user,
        metadata=metadata or {}
    )


def get_status_history(instance):
    """
    Get status history for a model instance.
    
    Args:
        instance: Model instance
    
    Returns:
        QuerySet of StatusHistory records
    """
    content_type = ContentType.objects.get_for_model(instance)
    return StatusHistory.objects.filter(
        content_type=content_type,
        object_id=instance.pk
    )


def get_action_log(instance):
    """
    Get action log for a model instance.
    
    Args:
        instance: Model instance
    
    Returns:
        QuerySet of ActionLog records
    """
    content_type = ContentType.objects.get_for_model(instance)
    return ActionLog.objects.filter(
        content_type=content_type,
        object_id=instance.pk
    )


def create_notification(
    title,
    message,
    recipient=None,
    audience=None,
    campus=None,
    priority=Notification.NORMAL,
    link='',
    created_by=None,
    expires_at=None
):
    """
    Create a notification.
    
    Args:
        title: Notification title
        message: Notification message
        recipient: Specific user to notify (optional)
        audience: Target audience group (optional)
        campus: Campus-specific notification (optional)
        priority: Priority level
        link: Optional link to related page
        created_by: User who created the notification
        expires_at: Optional expiration datetime
    
    Returns:
        Notification instance
    """
    return Notification.objects.create(
        title=title,
        message=message,
        recipient=recipient,
        audience=audience or Notification.ALL,
        campus=campus,
        priority=priority,
        link=link,
        created_by=created_by,
        expires_at=expires_at
    )


def get_user_notifications(user, unread_only=False):
    """
    Get notifications for a user.
    
    Args:
        user: User instance
        unread_only: If True, only return unread notifications
    
    Returns:
        QuerySet of Notification records
    """
    from apps.tenant.users.models import Role
    
    # Get user roles
    user_roles = []
    if hasattr(user, 'roles'):
        user_roles = [role.name for role in user.roles.all()]
    
    # Build query
    from django.db.models import Q
    query = Q(recipient=user)
    
    # Add audience-based notifications
    if Role.ADMIN in user_roles:
        query |= Q(audience=Notification.ADMIN)
    if Role.CAMPUS_ADMIN in user_roles:
        query |= Q(audience=Notification.CAMPUS_ADMIN)
    if Role.TEACHER in user_roles:
        query |= Q(audience=Notification.TEACHERS)
    if Role.STUDENT in user_roles:
        query |= Q(audience=Notification.STUDENTS)
    if Role.PARENT in user_roles:
        query |= Q(audience=Notification.PARENTS)
    
    # All users
    query |= Q(audience=Notification.ALL)
    
    notifications = Notification.objects.filter(query)
    
    if unread_only:
        notifications = notifications.filter(is_read=False)
    
    return notifications.distinct()
