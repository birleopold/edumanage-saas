from urllib.parse import urlencode

from django.contrib.auth.hashers import check_password
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant.academics.models import Enrollment
from apps.tenant.orgsettings.services import (
    selected_campus_id_from_request,
    update_current_campus_from_request,
)
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .models import Assessment, AssessmentScore
from .parent_session import PIN_SESSION_KEY


def _parent_allowed_student_ids(request, parent: ParentProfile):
    update_current_campus_from_request(request)
    campus_id = selected_campus_id_from_request(request)
    qs = ParentStudentLink.objects.filter(parent=parent)
    if campus_id:
        qs = qs.filter(student__campus_id=campus_id)
    return list(qs.values_list("student_id", flat=True))


def _pin_unlocked(request, parent_id: int) -> bool:
    blob = request.session.get(PIN_SESSION_KEY) or {}
    if int(blob.get("parent_id", 0)) != int(parent_id):
        return False
    exp = float(blob.get("expires_at", 0))
    if exp < timezone.now().timestamp():
        request.session.pop(PIN_SESSION_KEY, None)
        return False
    return True


def _set_pin_unlocked(request, parent_id: int) -> None:
    request.session[PIN_SESSION_KEY] = {
        "parent_id": int(parent_id),
        "expires_at": timezone.now().timestamp() + 8 * 3600,
    }


@role_required(Role.PARENT)
def results_home(request):
    parent = ParentProfile.objects.filter(user=request.user).first()
    if not parent:
        return HttpResponseForbidden("No parent profile linked to this account.")

    student_ids = _parent_allowed_student_ids(request, parent)
    if not student_ids:
        raise Http404("No linked students for this filter.")

    raw_sid = request.GET.get("student")
    if raw_sid:
        try:
            sid = int(raw_sid)
        except (TypeError, ValueError):
            sid = None
        if sid not in student_ids:
            raise Http404("Student not linked to your account.")
    else:
        sid = student_ids[0]

    student = get_object_or_404(StudentProfile.objects.select_related("campus"), pk=sid)

    if parent.results_access_pin_hash:
        if not _pin_unlocked(request, parent.pk):
            if request.method == "POST":
                pin = (request.POST.get("pin") or "").strip()
                if pin and check_password(pin, parent.results_access_pin_hash):
                    _set_pin_unlocked(request, parent.pk)
                    q = urlencode({"student": str(student.pk)})
                    return redirect(f"{request.path}?{q}")
                return render(
                    request,
                    "portals/parent/results/pin_gate.html",
                    {
                        "parent": parent,
                        "student": student,
                        "error": "Incorrect PIN. Try again or contact the school.",
                    },
                )
            return render(
                request,
                "portals/parent/results/pin_gate.html",
                {"parent": parent, "student": student, "error": ""},
            )

    enrollments = (
        Enrollment.objects.select_related(
            "offering",
            "offering__course",
            "offering__term",
            "offering__term__year",
        )
        .filter(student=student, status=Enrollment.ACTIVE)
        .order_by("offering__term__year__name", "offering__term__order", "offering__course__name")
    )

    offering_ids = list(enrollments.values_list("offering_id", flat=True))

    assessments = (
        Assessment.objects.select_related(
            "offering",
            "offering__course",
            "offering__term",
            "offering__term__year",
        )
        .filter(offering_id__in=offering_ids, is_published=True)
        .order_by("offering__term__year__name", "offering__term__order", "name")
    )

    scores = AssessmentScore.objects.filter(assessment__in=assessments, student=student)
    score_map = {s.assessment_id: s for s in scores}

    children = list(
        StudentProfile.objects.filter(pk__in=student_ids).order_by("last_name", "first_name")
    )

    return render(
        request,
        "portals/parent/results/home.html",
        {
            "parent": parent,
            "student": student,
            "children": children,
            "enrollments": enrollments,
            "assessments": assessments,
            "score_map": score_map,
        },
    )
