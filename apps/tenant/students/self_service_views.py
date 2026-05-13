from django.http import HttpResponse, HttpResponseForbidden

from apps.tenant.orgsettings.services import get_or_create_organization
from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .pdf_id_card import generate_student_id_card_pdf


@role_required(Role.STUDENT)
def student_id_card_self(request):
    student = StudentProfile.objects.filter(user=request.user).select_related("campus").first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")
    org = get_or_create_organization()
    buf = generate_student_id_card_pdf(student=student, org=org)
    response = HttpResponse(buf.read(), content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="student_id.pdf"'
    return response
