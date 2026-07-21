from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.orgsettings.utils import log_action
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.users.models import PasswordSetupToken, Role, User

from .forms import ParentProfileForm, ParentStudentLinkForm
from .services import link_parent_to_student
from .views import _editable_parents_queryset_for, _generate_unique_username


@admin_portal_required
def parent_create(request):
    """Create a parent and the first learner relationship in one workflow."""

    scoped = get_user_campus_scope(request.user)
    if request.method == "POST":
        form = ParentProfileForm(
            request.POST,
            campus_scope=scoped,
            include_student_link=True,
        )
        if form.is_valid():
            with transaction.atomic():
                parent = form.save(commit=False)
                create_user = form.cleaned_data.get("create_user")
                send_email_flag = form.cleaned_data.get("send_email")
                temp_password = None

                if create_user and parent.user_id is None:
                    email_prefix = parent.email.split("@")[0] if parent.email else ""
                    name_prefix = f"{parent.first_name}.{parent.last_name}".lower().replace(" ", "")
                    username = _generate_unique_username(email_prefix or name_prefix or "parent")
                    temp_password = User.objects.make_random_password(length=12)
                    user = User.objects.create(
                        username=username,
                        email=parent.email or "",
                        first_name=parent.first_name,
                        last_name=parent.last_name,
                    )
                    user.set_password(temp_password)
                    user.must_change_password = True
                    user.save(update_fields=["password", "must_change_password"])

                    role, _ = Role.objects.get_or_create(
                        code=Role.PARENT,
                        defaults={"name": "Parent"},
                    )
                    user.roles.add(role)
                    parent.user = user

                parent.save()
                link = link_parent_to_student(
                    parent=parent,
                    student=form.cleaned_data["student"],
                    relationship=form.cleaned_data["relationship"],
                    is_primary=form.cleaned_data.get("is_primary_guardian", False),
                )

                if form.cleaned_data.get("clear_results_pin"):
                    parent.results_access_pin_hash = ""
                elif form.cleaned_data.get("results_pin"):
                    parent.results_access_pin_hash = make_password(
                        form.cleaned_data["results_pin"]
                    )
                if form.cleaned_data.get("clear_results_pin") or form.cleaned_data.get(
                    "results_pin"
                ):
                    parent.save(update_fields=["results_access_pin_hash"])

                log_action(
                    parent,
                    action="STUDENT_LINKED",
                    description=f"Linked to {link.student} as {link.relationship}.",
                    user=request.user,
                    metadata={
                        "student_id": link.student_id,
                        "relationship": link.relationship,
                        "is_primary": link.is_primary,
                    },
                )

                if parent.user_id and temp_password:
                    if parent.email and send_email_flag:
                        setup_token = PasswordSetupToken.create_for_user(
                            parent.user,
                            created_by=request.user,
                        )
                        setup_url = request.build_absolute_uri(
                            f"/users/setup/{setup_token.token}/"
                        )
                        send_mail(
                            subject="Set Up Your Parent Portal Account",
                            message=(
                                f"Hello {parent.first_name},\n\n"
                                f"Your username: {parent.user.username}\n\n"
                                f"Click the link below to set your password:\n{setup_url}\n\n"
                                "This link is valid for 72 hours and can only be used once.\n\n"
                                "If you did not request this, please contact your administrator."
                            ),
                            from_email=None,
                            recipient_list=[parent.email],
                            fail_silently=True,
                        )
                        messages.success(
                            request,
                            "Parent created, learner linked and password setup link sent.",
                        )
                        return redirect("admin_parents_edit", pk=parent.pk)

                    request.session[f"parent_temp_password_{parent.pk}"] = temp_password
                    messages.success(
                        request,
                        "Parent created and linked to the learner. Print or copy login details now.",
                    )
                    return redirect("admin_parents_credentials", pk=parent.pk)

            messages.success(request, "Parent created and linked to the learner.")
            return redirect("admin_parents_edit", pk=parent.pk)
    else:
        form = ParentProfileForm(
            campus_scope=scoped,
            include_student_link=True,
        )

    return render(
        request,
        "portals/admin/parents/form.html",
        {"form": form, "mode": "create"},
    )


@admin_portal_required
def parent_add_student(request, pk: int):
    scoped = get_user_campus_scope(request.user)
    parent = get_object_or_404(_editable_parents_queryset_for(request.user), pk=pk)
    if request.method != "POST":
        return redirect("admin_parents_edit", pk=parent.pk)

    form = ParentStudentLinkForm(request.POST, campus_scope=scoped)
    if form.is_valid():
        link = link_parent_to_student(
            parent=parent,
            student=form.cleaned_data["student"],
            relationship=form.cleaned_data["relationship"],
            is_primary=form.cleaned_data.get("is_primary", False),
        )
        messages.success(
            request,
            f"{link.student} is now linked to {parent}.",
        )
    else:
        messages.error(request, "Choose a learner and relationship before linking.")
    return redirect("admin_parents_edit", pk=parent.pk)
