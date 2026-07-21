from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.parents.forms import StudentGuardianLinkForm
from apps.tenant.parents.models import ParentStudentLink
from apps.tenant.parents.services import link_parent_to_student
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required

from .views import _student_queryset_for


@admin_portal_required
def student_guardians(request, pk: int):
    student = get_object_or_404(_student_queryset_for(request.user), pk=pk)
    campus_scope = get_user_campus_scope(request.user)

    if request.method == "POST":
        form = StudentGuardianLinkForm(request.POST, campus_scope=campus_scope)
        if form.is_valid():
            link = link_parent_to_student(
                parent=form.cleaned_data["parent"],
                student=student,
                relationship=form.cleaned_data["relationship"],
                is_primary=form.cleaned_data.get("is_primary", False),
            )
            messages.success(
                request,
                f"{link.parent} is now linked to {student}.",
            )
            return redirect("admin_student_guardians", pk=student.pk)
    else:
        form = StudentGuardianLinkForm(campus_scope=campus_scope)

    links = (
        ParentStudentLink.objects.filter(student=student)
        .select_related("parent", "parent__user")
        .order_by("-is_primary", "parent__last_name", "parent__first_name")
    )
    return render(
        request,
        "portals/admin/students/guardians.html",
        {
            "student": student,
            "links": links,
            "form": form,
        },
    )


@admin_portal_required
def student_guardian_remove(request, pk: int, link_id: int):
    student = get_object_or_404(_student_queryset_for(request.user), pk=pk)
    link = get_object_or_404(
        ParentStudentLink.objects.select_related("parent"),
        pk=link_id,
        student=student,
    )
    if request.method == "POST":
        parent_name = str(link.parent)
        link.delete()
        messages.success(request, f"Removed {parent_name} from {student}'s guardians.")
    return redirect("admin_student_guardians", pk=student.pk)
