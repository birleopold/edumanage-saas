from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect

from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required

from .forms import ParentStudentLinkForm
from .link_services import remove_guardian_link, save_guardian_link
from .models import ParentStudentLink
from .views import _editable_parents_queryset_for


@admin_portal_required
def parent_add_student(request, pk: int):
    scoped = get_user_campus_scope(request.user)
    parent = get_object_or_404(_editable_parents_queryset_for(request.user), pk=pk)
    if request.method != "POST":
        return redirect("admin_parents_edit", pk=parent.pk)

    form = ParentStudentLinkForm(request.POST, campus_scope=scoped)
    if form.is_valid():
        link, created, demoted_count = save_guardian_link(
            parent=parent,
            student=form.cleaned_data["student"],
            relationship=form.cleaned_data.get("relationship") or "",
            is_primary=bool(form.cleaned_data.get("is_primary")),
            changed_by=request.user,
        )
        verb = "linked" if created else "updated"
        extra = " Previous primary guardian status was cleared." if demoted_count else ""
        messages.success(
            request,
            f"Guardian relationship {verb} for {link.student.get_full_name()}.{extra}",
        )
    else:
        messages.error(request, "The guardian relationship could not be saved. Review the selected student and details.")
    return redirect("admin_parents_edit", pk=parent.pk)


@admin_portal_required
def parent_remove_student(request, pk: int, link_id: int):
    parent = get_object_or_404(_editable_parents_queryset_for(request.user), pk=pk)
    links = ParentStudentLink.objects.filter(parent=parent).select_related("student", "parent")
    scoped = get_user_campus_scope(request.user)
    if scoped is not None:
        links = links.filter(student__campus=scoped)
    link = get_object_or_404(links, pk=link_id)

    if request.method == "POST":
        student_name = link.student.get_full_name()
        remove_guardian_link(link=link, changed_by=request.user)
        messages.success(request, f"Guardian relationship removed from {student_name}.")
    return redirect("admin_parents_edit", pk=parent.pk)
