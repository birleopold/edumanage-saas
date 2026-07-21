from django.db import transaction

from .models import ParentStudentLink


@transaction.atomic
def link_parent_to_student(
    *,
    parent,
    student,
    relationship: str = "",
    is_primary: bool = False,
):
    """Create or update a guardian relationship without duplicating links.

    A learner can have several parents or guardians, but selecting a new primary
    guardian removes the primary flag from the learner's other links.
    """

    if is_primary:
        ParentStudentLink.objects.filter(
            student=student,
            is_primary=True,
        ).exclude(parent=parent).update(is_primary=False)

    link, _ = ParentStudentLink.objects.update_or_create(
        parent=parent,
        student=student,
        defaults={
            "relationship": (relationship or "").strip(),
            "is_primary": bool(is_primary),
        },
    )
    return link
