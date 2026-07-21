from django.contrib import messages
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import redirect, render

from apps.tenant.orgsettings.utils import log_action
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.users.models import PasswordSetupToken, Role, User

from .create_forms import ParentCreateForm
from .models import ParentStudentLink
from .views import _generate_unique_username


@admin_portal_required
def parent_create(request):
    campus_scope = get_user_campus_scope(request.user)

    if request.method == "POST":
        form = ParentCreateForm(request.POST, campus_scope=campus_scope)
        if form.is_valid():
            with transaction.atomic():
                parent = form.save(commit=False)
                create_user = form.cleaned_data.get("create_user")
                send_email_flag = form.cleaned_data.get("send_email")
                student = form.cleaned_data["student"]
                relationship = (form.cleaned_data.get("relationship") or "").strip()
                is_primary = bool(form.cleaned_data.get("is_primary_guardian"))

                temp_password = None
                if create_user and parent.user_id is None:
                    base = (parent.email.split("@")[0] if parent.email else "parent") or "parent"
                    username = _generate_unique_username(base)
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
                    role, _ = Role.objects.get_or_create(code=Role.PARENT, defaults={"name": "Parent"})
                    user.roles.add(role)
                    parent.user = user

                parent.save()

                if is_primary:
                    ParentStudentLink.objects.filter(student=student, is_primary=True).update(is_primary=False)
                ParentStudentLink.objects.update_or_create(
                    parent=parent,
                    student=student,
                    defaults={"relationship": relationship, "is_primary": is_primary},
                )

                log_action(
                    parent,
                    action="STUDENT_LINKED",
                    description=f"Parent linked to {student} as {relationship or 'guardian'}.",
                    user=request.user,
                    metadata={
                        "student_id": student.pk,
                        "student_number": student.student_id,
                        "relationship": relationship,
                        "is_primary": is_primary,
                    },
                )

                results_pin = form.cleaned_data.get("results_pin")
                clear_results_pin = form.cleaned_data.get("clear_results_pin")
                if clear_results_pin:
                    parent.results_access_pin_hash = ""
                    parent.save(update_fields=["results_access_pin_hash"])
                elif results_pin:
                    from django.contrib.auth.hashers import make_password

                    parent.results_access_pin_hash = make_password(results_pin)
                    parent.save(update_fields=["results_access_pin_hash"])

                if parent.user_id and temp_password:
                    if parent.email and send_email_flag:
                        setup_token = PasswordSetupToken.create_for_user(parent.user, created_by=request.user)
                        setup_url = request.build_absolute_uri(f"/users/setup/{setup_token.token}/")
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
                        log_action(
                            parent,
                            action="CREDENTIALS_ISSUED",
                            description="Parent setup link sent via email.",
                            user=request.user,
                            metadata={"delivery": "email_secure_link", "username": parent.user.username},
                        )
                        messages.success(request, f"Parent created and linked to {student}. Setup email sent.")
                        return redirect("admin_parents_edit", pk=parent.pk)

                    request.session[f"parent_temp_password_{parent.pk}"] = temp_password
                    log_action(
                        parent,
                        action="CREDENTIALS_ISSUED",
                        description="Parent credentials issued for printing.",
                        user=request.user,
                        metadata={"delivery": "print", "username": parent.user.username},
                    )
                    messages.success(request, f"Parent created and linked to {student}.")
                    return redirect("admin_parents_credentials", pk=parent.pk)

            messages.success(request, f"Parent created and linked to {student}.")
            return redirect("admin_parents_edit", pk=parent.pk)
    else:
        form = ParentCreateForm(campus_scope=campus_scope)

    return render(
        request,
        "portals/admin/parents/form.html",
        {
            "form": form,
            "mode": "create",
            "form_submit_text": "Save Parent and Link Student",
        },
    )
