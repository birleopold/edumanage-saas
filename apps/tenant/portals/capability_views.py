from django.shortcuts import render
from django.urls import reverse

from apps.tenant.users.models import Role

from .capability_catalog import build_capability_context
from .permissions import admin_portal_required, role_required


def _render_capabilities(request, *, role: str, template_name: str, context=None):
    context = context or build_capability_context(request.user, role=role)
    return render(request, template_name, context)


def _apply_campus_safe_actions(context):
    """Replace institution-only Phase 7 links with existing campus-scoped hostel operations."""
    for phase in context["capability_phases"]:
        if phase["number"] != 7:
            continue
        phase["actions"] = [
            {
                "label": "Hostels and bed allocations",
                "url": reverse("admin_bed_allocations_list"),
                "description": "Campus-scoped placement operations",
                "primary": True,
            }
        ]
        phase["available"] = True
        phase["status_label"] = "Available in your portal"
    context["capability_available_count"] = sum(1 for phase in context["capability_phases"] if phase["available"])
    context["capability_managed_count"] = sum(1 for phase in context["capability_phases"] if not phase["available"])
    context["capability_action_count"] = sum(len(phase["actions"]) for phase in context["capability_phases"])
    return context


@admin_portal_required
def admin_capabilities(request):
    role = "admin" if request.user.is_superuser or request.user.has_role(Role.ADMIN) else "campus_admin"
    context = build_capability_context(request.user, role=role)
    if role == "campus_admin":
        context = _apply_campus_safe_actions(context)
    return _render_capabilities(
        request,
        role=role,
        template_name="portals/admin/capabilities.html",
        context=context,
    )


@role_required(Role.TEACHER)
def teacher_capabilities(request):
    return _render_capabilities(
        request,
        role="teacher",
        template_name="portals/teacher/capabilities.html",
    )


@role_required(Role.STUDENT)
def student_capabilities(request):
    return _render_capabilities(
        request,
        role="student",
        template_name="portals/student/capabilities.html",
    )


@role_required(Role.PARENT)
def parent_capabilities(request):
    return _render_capabilities(
        request,
        role="parent",
        template_name="portals/parent/capabilities.html",
    )
