from django.contrib import messages
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_current_campus, get_or_create_organization
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.orgsettings.utils import log_action
from apps.tenant.users.models import Role, User, PasswordSetupToken

from .forms import TeacherProfileForm
from .models import TeacherProfile


def _generate_unique_username(base: str) -> str:
    base = (base or "teacher").strip() or "teacher"
    username = base
    i = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{i}"
        i += 1
    return username


def _campus_queryset():
    org = get_or_create_organization()
    return Campus.objects.filter(organization=org).order_by("name")


def _campus_queryset_for(user):
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        return Campus.objects.filter(pk=scoped.pk)
    return _campus_queryset()


def _teacher_queryset_for(user):
    qs = TeacherProfile.objects.select_related("campus", "user")
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(campus=scoped)
    return qs


@admin_portal_required
def teacher_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page_raw = request.GET.get("per_page")
    page_number = request.GET.get("page") or 1

    scoped = get_user_campus_scope(request.user)
    campuses = _campus_queryset_for(request.user)
    current = scoped or get_current_campus(request)

    if scoped is not None:
        campus_id = scoped.id
    elif "campus" in request.GET:
        campus_filter = request.GET.get("campus")
        if campus_filter == "":
            campus_id = None
        else:
            try:
                campus_id = int(campus_filter)
            except (TypeError, ValueError):
                campus_id = None
    else:
        campus_id = current.id if current else None

    teachers_qs = _teacher_queryset_for(request.user)
    if campus_id:
        teachers_qs = teachers_qs.filter(campus_id=campus_id)
    if q:
        teachers_qs = teachers_qs.filter(
            Q(staff_id__icontains=q)
            | Q(first_name__icontains=q)
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

    paginator = Paginator(teachers_qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/teachers/list.html",
        {
            "teachers": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "campuses": campuses,
            "selected_campus_id": campus_id,
        },
    )


@admin_portal_required
def teacher_create(request):
    scoped = get_user_campus_scope(request.user)
    current = scoped or get_current_campus(request)
    campus_qs = _campus_queryset_for(request.user)
    if request.method == "POST":
        form = TeacherProfileForm(request.POST, campus_queryset=campus_qs)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                if obj.campus_id is None and current is not None:
                    obj.campus = current
                if scoped is not None and obj.campus_id != scoped.id:
                    return HttpResponseForbidden("You cannot create teachers outside your campus scope.")

                create_user = form.cleaned_data.get("create_user")
                send_email_flag = form.cleaned_data.get("send_email")

                temp_password = None
                if create_user and obj.user_id is None:
                    base = (obj.staff_id or (obj.email.split("@")[0] if obj.email else "teacher")).strip() or "teacher"
                    username = _generate_unique_username(base)
                    temp_password = User.objects.make_random_password(length=12)
                    user = User.objects.create(username=username, email=obj.email or "")
                    user.set_password(temp_password)
                    user.must_change_password = True
                    user.save(update_fields=["password", "must_change_password"])

                    role, _ = Role.objects.get_or_create(code=Role.TEACHER, defaults={"name": "Teacher"})
                    user.roles.add(role)
                    obj.user = user

                obj.save()

                if obj.user_id and temp_password:
                    if obj.email and send_email_flag:
                        setup_token = PasswordSetupToken.create_for_user(obj.user, created_by=request.user)
                        setup_url = request.build_absolute_uri(f"/users/setup/{setup_token.token}/")
                        send_mail(
                            subject="Set Up Your Teacher Portal Account",
                            message=(
                                f"Hello {obj.first_name},\n\n"
                                f"Your username: {obj.user.username if obj.user else ''}\n\n"
                                f"Click the link below to set your password:\n{setup_url}\n\n"
                                "This link is valid for 72 hours and can only be used once.\n\n"
                                "If you did not request this, please contact your administrator."
                            ),
                            from_email=None,
                            recipient_list=[obj.email],
                            fail_silently=True,
                        )
                        log_action(
                            obj,
                            action="CREDENTIALS_ISSUED",
                            description="Teacher setup link sent via email.",
                            user=request.user,
                            metadata={
                                "delivery": "email_secure_link",
                                "username": obj.user.username if obj.user_id else "",
                            },
                        )
                        return redirect("admin_teachers_list")

                    request.session[f"teacher_temp_password_{obj.pk}"] = temp_password
                    log_action(
                        obj,
                        action="CREDENTIALS_ISSUED",
                        description="Teacher credentials issued for printing.",
                        user=request.user,
                        metadata={
                            "delivery": "print",
                            "username": obj.user.username if obj.user_id else "",
                        },
                    )
                    return redirect("admin_teachers_credentials", pk=obj.pk)

            return redirect("admin_teachers_list")
    else:
        form = TeacherProfileForm(campus_queryset=campus_qs)
        if current is not None:
            form.fields["campus"].initial = current
    return render(request, "portals/admin/teachers/form.html", {"form": form, "mode": "create"})


@admin_portal_required
def teacher_credentials(request, pk: int):
    teacher = get_object_or_404(_teacher_queryset_for(request.user), pk=pk)
    temp_password = request.session.pop(f"teacher_temp_password_{teacher.pk}", None)
    log_action(
        teacher,
        action="CREDENTIALS_VIEWED",
        description="Teacher credentials screen viewed.",
        user=request.user,
        metadata={
            "username": teacher.user.username if teacher.user_id else "",
            "password_available": bool(temp_password),
        },
    )
    return render(
        request,
        "portals/admin/teachers/credentials.html",
        {"teacher": teacher, "temp_password": temp_password},
    )


@admin_portal_required
def teacher_edit(request, pk: int):
    scoped = get_user_campus_scope(request.user)
    campus_qs = _campus_queryset_for(request.user)
    teacher = get_object_or_404(_teacher_queryset_for(request.user), pk=pk)
    
    if request.method == "POST":
        if "reset_password" in request.POST:
            if not teacher.user_id:
                messages.error(request, "This teacher does not have a user account.")
                return redirect("admin_teachers_edit", pk=pk)
            
            if not teacher.email:
                messages.error(request, "This teacher does not have an email address.")
                return redirect("admin_teachers_edit", pk=pk)
            
            setup_token = PasswordSetupToken.create_for_user(teacher.user, created_by=request.user)
            setup_url = request.build_absolute_uri(f"/users/setup/{setup_token.token}/")
            
            send_mail(
                subject="Reset Your Teacher Portal Password",
                message=(
                    f"Hello {teacher.first_name},\n\n"
                    f"Your username: {teacher.user.username}\n\n"
                    f"Click the link below to reset your password:\n{setup_url}\n\n"
                    "This link is valid for 72 hours and can only be used once.\n\n"
                    "If you did not request this, please contact your administrator."
                ),
                from_email=None,
                recipient_list=[teacher.email],
                fail_silently=True,
            )
            
            log_action(
                teacher,
                action="PASSWORD_RESET",
                description="Password reset link sent to teacher.",
                user=request.user,
                metadata={
                    "delivery": "email_secure_link",
                    "username": teacher.user.username,
                },
            )
            
            messages.success(request, "Password reset link sent to teacher's email.")
            return redirect("admin_teachers_edit", pk=pk)
        
        form = TeacherProfileForm(request.POST, instance=teacher, campus_queryset=campus_qs)
        if form.is_valid():
            obj = form.save(commit=False)
            if scoped is not None and obj.campus_id != scoped.id:
                return HttpResponseForbidden("You cannot move teachers outside your campus scope.")
            obj.save()
            messages.success(request, "Teacher updated successfully.")
            return redirect("admin_teachers_list")
    else:
        form = TeacherProfileForm(instance=teacher, campus_queryset=campus_qs)
    return render(
        request,
        "portals/admin/teachers/form.html",
        {"form": form, "mode": "edit", "teacher": teacher},
    )
