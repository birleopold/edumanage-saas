from __future__ import annotations

from django import template
from django.db.models import Q

from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile


register = template.Library()


def _selected_campus_id(value):
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _scope_queryset(queryset, request, selected_campus):
    try:
        campus = get_user_campus_scope(request.user)
    except Exception:
        campus = None

    if campus is not None:
        return queryset.filter(campus=campus)

    campus_id = _selected_campus_id(selected_campus)
    if campus_id:
        return queryset.filter(campus_id=campus_id)
    return queryset


@register.simple_tag(takes_context=True)
def registry_summary(context, kind: str, selected_campus=None):
    """Return compact, campus-safe counts for student and teacher registries."""

    request = context.get("request")
    if request is None or not getattr(request, "user", None):
        return {"total": 0, "active": 0, "portal": 0, "attention": 0}

    normalized_kind = (kind or "").strip().lower()
    if normalized_kind == "student":
        queryset = _scope_queryset(StudentProfile.objects.all(), request, selected_campus)
        return {
            "total": queryset.count(),
            "active": queryset.filter(is_active=True).count(),
            "portal": queryset.filter(user__isnull=False).count(),
            "attention": queryset.filter(
                Q(is_active=False) | Q(user__isnull=True) | Q(student_id="")
            ).distinct().count(),
        }

    if normalized_kind == "teacher":
        queryset = _scope_queryset(TeacherProfile.objects.all(), request, selected_campus)
        return {
            "total": queryset.count(),
            "active": queryset.filter(is_active=True).count(),
            "portal": queryset.filter(user__isnull=False).count(),
            "attention": queryset.filter(
                Q(is_active=False) | Q(user__isnull=True) | Q(email="")
            ).distinct().count(),
        }

    return {"total": 0, "active": 0, "portal": 0, "attention": 0}
