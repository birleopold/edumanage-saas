"""
Utility functions for core functionality.
"""
from django.contrib.contenttypes.models import ContentType

from .models import ActionLog, StatusHistory


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
