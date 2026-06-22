from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.students.models import StudentProfile

from .models import StudentTransportAssignment


def parent_items(user, campus_id=None):
    parent = ParentProfile.objects.filter(user=user).first()
    if not parent:
        return StudentTransportAssignment.objects.none()
    links = ParentStudentLink.objects.filter(parent=parent)
    if campus_id:
        links = links.filter(student__campus_id=campus_id)
    return StudentTransportAssignment.objects.select_related("student", "route", "stop", "route__vehicle").filter(
        student_id__in=links.values_list("student_id", flat=True)
    ).order_by("student__last_name", "student__first_name", "-created_at")


def learner_items(user):
    student = StudentProfile.objects.filter(user=user).select_related("campus").first()
    if not student:
        return StudentTransportAssignment.objects.none(), None
    return StudentTransportAssignment.objects.select_related("student", "route", "stop", "route__vehicle").filter(student=student).order_by("-created_at"), student
