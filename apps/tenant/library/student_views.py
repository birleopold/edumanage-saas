from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .models import BookLoan


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = request.GET.get("per_page")
    per_page = default
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = default
    return max(1, min(per_page, max_value))


@role_required(Role.STUDENT)
def my_loans(request):
    student = StudentProfile.objects.filter(user=request.user).select_related("campus").first()
    if not student:
        return HttpResponseForbidden("No student profile linked to this account.")

    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = BookLoan.objects.select_related("copy", "copy__book").filter(student=student)

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/student/library/loans_list.html",
        {"student": student, "loans": page_obj.object_list, "page_obj": page_obj, "per_page": per_page},
    )
