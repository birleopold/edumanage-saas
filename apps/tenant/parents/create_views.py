from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import redirect, render

from apps.tenant.orgsettings.utils import log_action
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.users.models import PasswordSetupToken, Role, User

from .forms import ParentProfileForm
from .models import ParentStudentLink


def _generate_unique_username(base: str) -> str:
    base = (base or "parent").strip() or "parent"
    username = base
    suffix = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{suffix}"
        suffix += 1
    return username


@admin_portal_required
def parent_create(request):
    """Create a guardian account and its first student relationship atomically."""
    scoped = get_user_campus_scope(request.user)

    if request.method == "POST":
        form = ParentProfileForm(
            request.POST,
            require_student_link=True,
            campus_scope=scoped,
        )
        if form.is_valid():
            with transaction.atomic():
                parent = form.save(commit=False)
                create_user = form.cleaned_data.get("create_user")
                send_email_flag = form.cleaned_data.get("send_email")
                student = form.cleaned_data["student"]
                relationship = form.cleaned_data["relationship"]
                is_primary = form.cleaned_data.get("is_primary_guardian", False)

                temp_password = None
                if create_user and parent.user_id is None:
                    base = (
                        parent.email.split("@")[0]
                        if parent.email
                        else f"parent-{student.student_id or student.pk}"
                    )
                    username = _generate_unique_username(base)
                    temp_password = User.objects.make_random_password(length=12)
                    user = User.objects.create(
                        username=username,
                        email=parent.email or "",
                        phone=parent.phone or "",
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
                link = ParentStudentLink.objects.create(
                    parent=parent,
                    student=student,
                    relationship=relationship,
                    is_primary=is_primary,
                )

                if form.cleaned_data.get("clear_results_pin"):
                    parent.results_access_pin_hash = ""
                elif form.cleaned_data.get("results_pin"):
                    parent.results_access_pin_hash = make_password(
                        form.cleaned_data["results_pin"]
                    )
                if form.cleaned_data.get("clear_results_pin") or form.cleaned_data.get("results_pin"):
                    parent.save(update_fields=["results_access_pin_hash"])

                activity_metadata = {
                    "parent_id": parent.pk,
                    "student_id": student.pk,
                    "student_number": student.student_id,
                    "relationship": relationship,
                    "is_primary": is_primary,
                    "link_id": link.pk,
                }
                log_action(
                    parent,
                    action="STUDENT_LINKED",
                    description=f"Linked to {student.get_full_name()} as {relationship}.",
                    user=request.user,
                    metadata=activity_metadata,
                )
                log_action(
                    student,
                    action="GUARDIAN_LINKED",
                    description=f"Guardian {parent.get_full_name()} linked as {relationship}.",
                    user=request.user,
                    metadata=activity_metadata,
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
                                f"You have been linked to {student.get_full_name()} "
                                f"({student.student_id or 'student record'}).\n\n"
                                f"Click the link below to set your password:\n{setup_url}\n\n"
                                "This link is valid for 72 hours and can only be used once.\n\n"
                                "If you did not request this, please contact your administrator."
                            ),
                            from_email=None,
                            recipient_list=[parent.email],
                            fail_silently=True,
                        )
                        log_action(
                            parent,
                            action="CREDENTIALS_ISSUED",
                            description="Parent setup link sent via email.",
                            user=request.user,
                            metadata={
                                "delivery": "email_secure_link",
                                "username": parent.user.username,
                            },
                        )
                        messages.success(
                            request,
                            "Parent created, linked to the student, and sent a setup email.",
                        )
                        return redirect("admin_parents_edit", pk=parent.pk)

                    request.session[f"parent_temp_password_{parent.pk}"] = temp_password
                    log_action(
                        parent,
                        action="CREDENTIALS_ISSUED",
                        description="Parent credentials issued for printing.",
                        user=request.user,
                        metadata={
                            "delivery": "print",
                            "username": parent.user.username,
                        },
                    )
                    messages.success(
                        request,
                        "Parent created and linked to the selected student. Print or copy the login details now.",
                    )
                    return redirect("admin_parents_credentials", pk=parent.pk)

                messages.success(
                    request,
                    "Parent created and linked to the selected student.",
                )
                return redirect("admin_parents_edit", pk=parent.pk)
    else:
        form = ParentProfileForm(
            require_student_link=True,
            campus_scope=scoped,
        )

    return render(
        request,
        "portals/admin/parents/form.html",
        {"form": form, "mode": "create"},
    )
