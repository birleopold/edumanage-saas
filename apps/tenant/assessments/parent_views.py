from urllib.parse import urlencode

from django.contrib.auth.hashers import check_password
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant.orgsettings.services import (
    selected_campus_id_from_request,
    update_current_campus_from_request,
)
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.portals.permissions import role_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.users.models import Role

from .parent_session import PIN_SESSION_KEY
from .services import build_report_card, parent_linked_students, published_assessments_for_student, score_map_for_student


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


def _parent_profile(request):
    return ParentProfile.objects.filter(user=request.user).first()


def _resolve_student_for_parent(request, parent: ParentProfile, student_id: int | None = None):
    student_ids = _parent_allowed_student_ids(request, parent)
    if not student_ids:
        raise Http404("No linked students for this filter.")

    sid = student_id
    if sid is None:
        raw_sid = request.GET.get("student")
        if raw_sid:
            try:
                sid = int(raw_sid)
            except (TypeError, ValueError):
                sid = None
        else:
            sid = student_ids[0]

    if sid not in student_ids:
        raise Http404("Student not linked to your account.")
    return get_object_or_404(StudentProfile.objects.select_related("campus", "stream", "stream__class_group"), pk=sid), student_ids


def _require_pin_or_render_gate(request, parent: ParentProfile, student: StudentProfile):
    if not parent.results_access_pin_hash:
        return None
    if _pin_unlocked(request, parent.pk):
        return None
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


@role_required(Role.PARENT)
def results_home(request):
    parent = _parent_profile(request)
    if not parent:
        return HttpResponseForbidden("No parent profile linked to this account.")

    student, student_ids = _resolve_student_for_parent(request, parent)
    gate_response = _require_pin_or_render_gate(request, parent, student)
    if gate_response is not None:
        return gate_response

    assessments = list(published_assessments_for_student(student))
    score_map = score_map_for_student(student, assessments)
    children = list(StudentProfile.objects.filter(pk__in=student_ids).order_by("last_name", "first_name"))

    return render(
        request,
        "portals/parent/results/home.html",
        {
            "parent": parent,
            "student": student,
            "children": children,
            "assessments": assessments,
            "score_map": score_map,
            "report": build_report_card(student),
        },
    )


@role_required(Role.PARENT)
def report_card(request, student_id: int):
    parent = _parent_profile(request)
    if not parent:
        return HttpResponseForbidden("No parent profile linked to this account.")

    student, student_ids = _resolve_student_for_parent(request, parent, student_id)
    gate_response = _require_pin_or_render_gate(request, parent, student)
    if gate_response is not None:
        return gate_response

    return render(
        request,
        "portals/parent/results/report_card.html",
        {
            "parent": parent,
            "student": student,
            "children": list(parent_linked_students(parent)),
            "report": build_report_card(student),
        },
    )


@role_required(Role.PARENT)
def report_card_print(request, student_id: int):
    parent = _parent_profile(request)
    if not parent:
        return HttpResponseForbidden("No parent profile linked to this account.")

    student, student_ids = _resolve_student_for_parent(request, parent, student_id)
    gate_response = _require_pin_or_render_gate(request, parent, student)
    if gate_response is not None:
        return gate_response

    return render(
        request,
        "portals/parent/results/report_card_print.html",
        {"parent": parent, "student": student, "report": build_report_card(student)},
    )
