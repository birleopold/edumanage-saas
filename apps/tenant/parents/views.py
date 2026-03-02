from django.contrib import messages
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.permissions import role_required
from apps.tenant.orgsettings.utils import log_action
from apps.tenant.users.models import Role, User, PasswordSetupToken

from .forms import ParentProfileForm, ParentStudentLinkForm
from .models import ParentProfile, ParentStudentLink


def _generate_unique_username(base: str) -> str:
    base = (base or "parent").strip() or "parent"
    username = base
    i = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{i}"
        i += 1
    return username


@role_required(Role.ADMIN)
def parent_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page_raw = request.GET.get("per_page")
    page_number = request.GET.get("page") or 1

    parents_qs = ParentProfile.objects.all()
    if q:
        parents_qs = parents_qs.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(phone__icontains=q)
            | Q(email__icontains=q)
        )

    per_page = 25
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = 25
    per_page = max(1, min(per_page, 200))

    paginator = Paginator(parents_qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/parents/list.html",
        {
            "parents": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
        },
    )


@role_required(Role.ADMIN)
def parent_create(request):
    if request.method == "POST":
        form = ParentProfileForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                parent = form.save(commit=False)

                create_user = form.cleaned_data.get("create_user")
                send_email_flag = form.cleaned_data.get("send_email")

                temp_password = None
                if create_user and parent.user_id is None:
                    base = (parent.email.split("@")[0] if parent.email else f"parent{parent.pk or ''}") or "parent"
                    username = _generate_unique_username(base)
                    temp_password = User.objects.make_random_password(length=12)
                    user = User.objects.create(username=username, email=parent.email or "")
                    user.set_password(temp_password)
                    user.must_change_password = True
                    user.save(update_fields=["password", "must_change_password"])

                    role, _ = Role.objects.get_or_create(code=Role.PARENT, defaults={"name": "Parent"})
                    user.roles.add(role)
                    parent.user = user

                parent.save()

                if parent.user_id and temp_password:
                    if parent.email and send_email_flag:
                        setup_token = PasswordSetupToken.create_for_user(parent.user, created_by=request.user)
                        setup_url = request.build_absolute_uri(f"/users/setup/{setup_token.token}/")
                        send_mail(
                            subject="Set Up Your Parent Portal Account",
                            message=(
                                f"Hello {parent.first_name},\n\n"
                                f"Your username: {parent.user.username if parent.user else ''}\n\n"
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
                                "username": parent.user.username if parent.user_id else "",
                            },
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
                            "username": parent.user.username if parent.user_id else "",
                        },
                    )
                    return redirect("admin_parents_credentials", pk=parent.pk)

            return redirect("admin_parents_edit", pk=parent.pk)
    else:
        form = ParentProfileForm()
    return render(request, "portals/admin/parents/form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def parent_credentials(request, pk: int):
    parent = get_object_or_404(ParentProfile, pk=pk)
    temp_password = request.session.pop(f"parent_temp_password_{parent.pk}", None)
    log_action(
        parent,
        action="CREDENTIALS_VIEWED",
        description="Parent credentials screen viewed.",
        user=request.user,
        metadata={
            "username": parent.user.username if parent.user_id else "",
            "password_available": bool(temp_password),
        },
    )
    return render(
        request,
        "portals/admin/parents/credentials.html",
        {"parent": parent, "temp_password": temp_password},
    )


@role_required(Role.ADMIN)
def parent_edit(request, pk: int):
    parent = get_object_or_404(ParentProfile, pk=pk)

    if request.method == "POST":
        if "reset_password" in request.POST:
            if not parent.user_id:
                messages.error(request, "This parent does not have a user account.")
                return redirect("admin_parents_edit", pk=pk)
            
            if not parent.email:
                messages.error(request, "This parent does not have an email address.")
                return redirect("admin_parents_edit", pk=pk)
            
            setup_token = PasswordSetupToken.create_for_user(parent.user, created_by=request.user)
            setup_url = request.build_absolute_uri(f"/users/setup/{setup_token.token}/")
            
            send_mail(
                subject="Reset Your Parent Portal Password",
                message=(
                    f"Hello {parent.first_name},\n\n"
                    f"Your username: {parent.user.username}\n\n"
                    f"Click the link below to reset your password:\n{setup_url}\n\n"
                    "This link is valid for 72 hours and can only be used once.\n\n"
                    "If you did not request this, please contact your administrator."
                ),
                from_email=None,
                recipient_list=[parent.email],
                fail_silently=True,
            )
            
            log_action(
                parent,
                action="PASSWORD_RESET",
                description="Password reset link sent to parent.",
                user=request.user,
                metadata={
                    "delivery": "email_secure_link",
                    "username": parent.user.username,
                },
            )
            
            messages.success(request, "Password reset link sent to parent's email.")
            return redirect("admin_parents_edit", pk=pk)
        
        form = ParentProfileForm(request.POST, instance=parent)
        if form.is_valid():
            form.save()
            messages.success(request, "Parent updated successfully.")
            return redirect("admin_parents_edit", pk=parent.pk)
    else:
        form = ParentProfileForm(instance=parent)

    links = ParentStudentLink.objects.filter(parent=parent).select_related("student")
    link_form = ParentStudentLinkForm()

    return render(
        request,
        "portals/admin/parents/form.html",
        {
            "form": form,
            "mode": "edit",
            "parent": parent,
            "links": links,
            "link_form": link_form,
        },
    )


@role_required(Role.ADMIN)
def parent_add_student(request, pk: int):
    parent = get_object_or_404(ParentProfile, pk=pk)
    if request.method != "POST":
        return redirect("admin_parents_edit", pk=parent.pk)

    form = ParentStudentLinkForm(request.POST)
    if form.is_valid():
        link = form.save(commit=False)
        link.parent = parent
        ParentStudentLink.objects.update_or_create(
            parent=parent,
            student=link.student,
            defaults={
                "relationship": link.relationship,
                "is_primary": link.is_primary,
            },
        )
    return redirect("admin_parents_edit", pk=parent.pk)


@role_required(Role.ADMIN)
def parent_remove_student(request, pk: int, link_id: int):
    parent = get_object_or_404(ParentProfile, pk=pk)
    link = get_object_or_404(ParentStudentLink, pk=link_id, parent=parent)
    if request.method == "POST":
        link.delete()
    return redirect("admin_parents_edit", pk=parent.pk)
