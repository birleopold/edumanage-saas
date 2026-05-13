from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404

from apps.tenant.orgsettings.services import (
    get_or_create_organization,
    selected_campus_id_from_request,
    update_current_campus_from_request,
)
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .pdf_id_card import generate_student_id_card_pdf


def _parent_allowed_student_ids(request, parent: ParentProfile):
    update_current_campus_from_request(request)
    campus_id = selected_campus_id_from_request(request)
    qs = ParentStudentLink.objects.filter(parent=parent)
    if campus_id:
        qs = qs.filter(student__campus_id=campus_id)
    return list(qs.values_list("student_id", flat=True))


@role_required(Role.PARENT)
def parent_child_id_card_pdf(request, student_pk: int):
    parent = ParentProfile.objects.filter(user=request.user).first()
    if not parent:
        return HttpResponseForbidden("No parent profile linked to this account.")
    allowed = _parent_allowed_student_ids(request, parent)
    if student_pk not in allowed:
        raise Http404("Student not linked to your account.")
    student = get_object_or_404(StudentProfile.objects.select_related("campus"), pk=student_pk)
    org = get_or_create_organization()
    buf = generate_student_id_card_pdf(student=student, org=org)
    response = HttpResponse(buf.read(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="student_{student_pk}_id.pdf"'
    return response
