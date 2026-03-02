from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render

from apps.tenant.academics.models import CourseOffering, Enrollment
from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role

from .forms import TeacherIncidentForm
from .models import Incident


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = request.GET.get("per_page")
    per_page = default
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = default
    return max(1, min(per_page, max_value))


@role_required(Role.TEACHER)
def my_incidents(request):
    teacher = TeacherProfile.objects.filter(user=request.user).first()
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Incident.objects.select_related("student").filter(reported_by=teacher)
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(category__icontains=q)
            | Q(student__first_name__icontains=q)
            | Q(student__last_name__icontains=q)
            | Q(student__student_id__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/teacher/discipline/incidents_list.html",
        {"teacher": teacher, "incidents": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.TEACHER)
def report_incident(request):
    teacher = TeacherProfile.objects.filter(user=request.user).first()
    if not teacher:
        return HttpResponseForbidden("No teacher profile linked to this account.")

    offering_ids = list(CourseOffering.objects.filter(teacher=teacher).values_list("id", flat=True))
    student_ids = list(
        Enrollment.objects.filter(offering_id__in=offering_ids, status=Enrollment.ACTIVE)
        .values_list("student_id", flat=True)
        .distinct()
    )
    students_qs = StudentProfile.objects.filter(id__in=student_ids).order_by("last_name", "first_name")

    if request.method == "POST":
        form = TeacherIncidentForm(request.POST)
        form.fields["student"].queryset = students_qs
        if form.is_valid():
            incident = form.save(commit=False)
            incident.reported_by = teacher
            incident.save()
            messages.success(request, "Incident reported.")
            return redirect("teacher_incidents_list")
    else:
        form = TeacherIncidentForm()
        form.fields["student"].queryset = students_qs

    return render(
        request,
        "portals/teacher/discipline/incident_report.html",
        {"teacher": teacher, "form": form},
    )
