"""
Notify administrators when a grievance is submitted (in-app + optional email).
"""
from django.conf import settings
from django.core.mail import send_mail

from apps.tenant.orgsettings.models import Notification
from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.orgsettings.utils import create_notification
from apps.tenant.users.models import Role


def notify_admins_new_grievance(grievance) -> None:
    """
    Broadcast to admin audience and email the organisation contact if configured.
    Safe to call after grievance is saved (needs grievance.pk).
    """
    org = get_or_create_organization()
    link = f"/admin/grievances/{grievance.pk}/"
    title = f"New grievance: {grievance.subject[:120]}"
    body_preview = (grievance.body or "")[:900]
    msg = (
        f"Submitted by: {grievance.submitted_by.get_full_name() or grievance.submitted_by.username}\n"
        f"Campus: {grievance.campus or '—'}\n\n"
        f"{body_preview}"
    )
    create_notification(
        title=title,
        message=msg,
        audience=Notification.ADMIN,
        campus=grievance.campus,
        priority=Notification.URGENT,
        link=link,
        created_by=grievance.submitted_by,
    )
    if grievance.campus_id:
        create_notification(
            title=title,
            message=msg,
            audience=Notification.CAMPUS_ADMIN,
            campus=grievance.campus,
            priority=Notification.URGENT,
            link=link,
            created_by=grievance.submitted_by,
        )

    to_email = (org.email or "").strip()
    if not to_email:
        return
    subject = f"[{org.name}] Grievance: {grievance.subject[:60]}"
    email_body = (
        f"{msg}\n\nOpen in EduManage admin: {link}\n"
        f"(Configure a public URL in production if links should be absolute.)"
    )
    send_mail(
        subject=subject,
        message=email_body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[to_email],
        fail_silently=True,
    )


def notify_grievance_submitter_status_change(grievance, *, old_status: str, actor) -> None:
    """
    In-app notification to the person who raised the concern when an admin changes status.
    """
    if old_status == grievance.status:
        return

    from .models import Grievance

    labels = dict(Grievance.STATUS_CHOICES)
    prev = labels.get(old_status, old_status)
    new = grievance.get_status_display()
    u = grievance.submitted_by

    if u.has_role(Role.PARENT):
        link = f"/parent/grievances/submissions/{grievance.pk}/"
    elif u.has_role(Role.TEACHER):
        link = f"/teacher/grievances/submissions/{grievance.pk}/"
    else:
        link = ""

    notes = (grievance.resolution_notes or "").strip()
    msg = f"Your concern is now: {new} (previously: {prev})."
    if notes:
        msg += f"\n\nNotes from the school:\n{notes[:800]}"

    create_notification(
        recipient=u,
        title=f"Concern update: {grievance.subject[:120]}",
        message=msg[:4000],
        audience=Notification.ALL,
        campus=None,
        priority=Notification.NORMAL,
        link=link,
        created_by=actor,
    )
