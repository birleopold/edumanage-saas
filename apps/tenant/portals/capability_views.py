from django.shortcuts import render

from apps.tenant.users.models import Role

from .capability_catalog import build_capability_context
from .permissions import admin_portal_required, role_required


def _render_capabilities(request, *, role: str, template_name: str):
    context = build_capability_context(request.user, role=role)
    return render(request, template_name, context)


@admin_portal_required
def admin_capabilities(request):
    role = "admin" if request.user.is_superuser or request.user.has_role(Role.ADMIN) else "campus_admin"
    return _render_capabilities(
        request,
        role=role,
        template_name="portals/admin/capabilities.html",
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
