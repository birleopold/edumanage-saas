from django.db import transaction

from apps.tenant.orgsettings.utils import log_action

from .models import ParentStudentLink


@transaction.atomic
def save_guardian_link(*, parent, student, relationship="", is_primary=False, changed_by=None):
    """Create/update one guardian relationship and consistently enforce primary status."""

    relationship = (relationship or "").strip()
    demoted_count = 0
    if is_primary:
        demoted_count = (
            ParentStudentLink.objects.select_for_update()
            .filter(student=student, is_primary=True)
            .exclude(parent=parent)
            .update(is_primary=False)
        )

    link, created = ParentStudentLink.objects.update_or_create(
        parent=parent,
        student=student,
        defaults={
            "relationship": relationship,
            "is_primary": bool(is_primary),
        },
    )

    metadata = {
        "parent_id": parent.pk,
        "student_id": student.pk,
        "student_number": student.student_id,
        "relationship": relationship,
        "is_primary": bool(is_primary),
        "link_id": link.pk,
        "created": created,
        "demoted_primary_links": demoted_count,
    }
    action = "STUDENT_LINKED" if created else "STUDENT_LINK_UPDATED"
    reciprocal_action = "GUARDIAN_LINKED" if created else "GUARDIAN_LINK_UPDATED"

    log_action(
        parent,
        action=action,
        description=f"Linked to {student.get_full_name()} as {relationship or 'guardian'}.",
        user=changed_by,
        metadata=metadata,
    )
    log_action(
        student,
        action=reciprocal_action,
        description=f"Guardian {parent.get_full_name()} linked as {relationship or 'guardian'}.",
        user=changed_by,
        metadata=metadata,
    )
    return link, created, demoted_count


@transaction.atomic
def remove_guardian_link(*, link, changed_by=None):
    """Remove a guardian relationship while preserving an audit event on both records."""

    parent = link.parent
    student = link.student
    metadata = {
        "parent_id": parent.pk,
        "student_id": student.pk,
        "student_number": student.student_id,
        "relationship": link.relationship,
        "is_primary": link.is_primary,
        "link_id": link.pk,
    }
    log_action(
        parent,
        action="STUDENT_UNLINKED",
        description=f"Unlinked from {student.get_full_name()}.",
        user=changed_by,
        metadata=metadata,
    )
    log_action(
        student,
        action="GUARDIAN_UNLINKED",
        description=f"Guardian {parent.get_full_name()} was unlinked.",
        user=changed_by,
        metadata=metadata,
    )
    link.delete()
