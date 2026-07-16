import csv

from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from django.contrib import messages

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_current_campus, get_or_create_organization
from apps.tenant.orgsettings.utils import log_action
from apps.tenant.users.models import Role, User, PasswordSetupToken
from apps.tenant.portals.campus_permissions import get_user_campus_scope, user_can_access_campus
from apps.tenant.portals.permissions import admin_portal_required

from .forms import StudentProfileForm
from .models import StudentProfile
from .pdf_id_card import generate_student_id_card_pdf
from .services import generate_next_student_id


def _campus_queryset():
    org = get_or_create_organization()
    return Campus.objects.filter(organization=org).order_by("name")


def _campus_queryset_for(user):
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        return Campus.objects.filter(pk=scoped.pk)
    return _campus_queryset()


def _student_queryset_for(user):
    qs = StudentProfile.objects.select_related("campus", "stream").all()
    scoped = get_user_campus_scope(user)
    if scoped is not None:
        qs = qs.filter(campus=scoped)
    return qs


def _students_queryset_for_list_filters(request):
    """
    Same campus + search rules as the student list (and CSV export).
    Returns (queryset, selected_campus_id, q).
    """
    q = (request.GET.get("q") or "").strip()
    scoped = get_user_campus_scope(request.user)
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

    students_qs = _student_queryset_for(request.user)
    if campus_id:
        students_qs = students_qs.filter(campus_id=campus_id)
    if q:
        students_qs = students_qs.filter(
            Q(student_id__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
        )
    return students_qs, campus_id, q


@admin_portal_required
def student_list(request):
    per_page_raw = request.GET.get("per_page")
    page_number = request.GET.get("page") or 1

    campuses = _campus_queryset_for(request.user)
    students_qs, campus_id, q = _students_queryset_for_list_filters(request)

    per_page = 25
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = 25
    per_page = max(1, min(per_page, 200))

    paginator = Paginator(students_qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/students/list.html",
        {
            "students": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "q": q,
            "per_page": per_page,
            "campuses": campuses,
            "selected_campus_id": campus_id,
        },
    )


@admin_portal_required
def student_export_csv(request):
    """Download students as CSV using the same campus and search filters as the list."""
    students_qs, _campus_id, _q = _students_queryset_for_list_filters(request)
    students_qs = students_qs.order_by("last_name", "first_name")

    filename = f"students_{timezone.now().strftime('%Y%m%d_%H%M')}.csv"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")

    writer = csv.writer(response)
    writer.writerow(
        [
            "student_id",
            "first_name",
            "last_name",
            "email",
            "campus",
            "stream",
            "date_of_birth",
            "district",
            "subcounty",
            "parish",
            "nin",
            "learner_id",
            "is_active",
            "created_at",
        ]
    )
    for s in students_qs.iterator():
        writer.writerow(
            [
                s.student_id or "",
                s.first_name or "",
                s.last_name or "",
                s.email or "",
                s.campus.name if s.campus_id else "",
                str(s.stream) if s.stream_id else "",
                s.date_of_birth.isoformat() if s.date_of_birth else "",
                s.district or "",
                s.subcounty or "",
                s.parish or "",
                s.nin or "",
                s.learner_id or "",
                "yes" if s.is_active else "no",
                s.created_at.isoformat() if s.created_at else "",
            ]
        )
    return response


@admin_portal_required
def student_create(request):
    scoped = get_user_campus_scope(request.user)
    current = scoped or get_current_campus(request)
    campus_qs = _campus_queryset_for(request.user)
    if request.method == "POST":
        form = StudentProfileForm(request.POST, campus=current, campus_queryset=campus_qs)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                if obj.campus_id is None and current is not None:
                    obj.campus = current
                if scoped is not None and obj.campus_id != scoped.id:
                    return HttpResponseForbidden("You cannot create students outside your campus scope.")

                if not obj.student_id:
                    obj.student_id = generate_next_student_id(obj.campus)

                create_user = form.cleaned_data.get("create_user")
                send_email_flag = form.cleaned_data.get("send_email")

                temp_password = None
                if create_user and obj.user_id is None:
                    temp_password = User.objects.make_random_password(length=12)
                    user = User.objects.create(username=obj.student_id, email=obj.email or "")
                    user.set_password(temp_password)
                    user.must_change_password = True
                    user.save(update_fields=["password", "must_change_password"])

                    student_role = Role.objects.filter(code=Role.STUDENT).first()
                    if student_role:
                        user.roles.add(student_role)

                    obj.user = user

                obj.save()

                if obj.user_id and temp_password:
                    if obj.email and send_email_flag:
                        setup_token = PasswordSetupToken.create_for_user(obj.user, created_by=request.user)
                        setup_url = request.build_absolute_uri(
                            f"/users/setup/{setup_token.token}/"
                        )
                        send_mail(
                            subject="Set Up Your Student Portal Account",
                            message=(
                                f"Hello {obj.first_name},\n\n"
                                f"Your student number: {obj.student_id}\n\n"
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
                            description="Student setup link sent via email.",
                            user=request.user,
                            metadata={
                                "delivery": "email_secure_link",
                                "username": obj.user.username if obj.user_id else "",
                                "student_id": obj.student_id,
                            },
                        )
                        messages.success(request, "Student created. Password setup link sent via email.")
                        return redirect("admin_students_list")

                    request.session[f"student_temp_password_{obj.pk}"] = temp_password
                    log_action(
                        obj,
                        action="CREDENTIALS_ISSUED",
                        description="Student credentials issued for printing.",
                        user=request.user,
                        metadata={
                            "delivery": "print",
                            "username": obj.user.username if obj.user_id else "",
                            "student_id": obj.student_id,
                        },
                    )
                    messages.success(request, "Student created. Print or copy login details now.")
                    return redirect("admin_students_credentials", pk=obj.pk)

            messages.success(request, "Student created.")
            return redirect("admin_students_list")
    else:
        form = StudentProfileForm(campus=current, campus_queryset=campus_qs)
        if current is not None:
            form.fields["campus"].initial = current
    return render(request, "portals/admin/students/form.html", {"form": form, "mode": "create"})


@admin_portal_required
def student_credentials(request, pk: int):
    student = get_object_or_404(_student_queryset_for(request.user), pk=pk)
    temp_password = request.session.pop(f"student_temp_password_{student.pk}", None)
    log_action(
        student,
        action="CREDENTIALS_VIEWED",
        description="Student credentials screen viewed.",
        user=request.user,
        metadata={
            "username": student.user.username if student.user_id else "",
            "student_id": student.student_id,
            "password_available": bool(temp_password),
        },
    )
    return render(
        request,
        "portals/admin/students/credentials.html",
        {"student": student, "temp_password": temp_password},
    )


@admin_portal_required
def student_id_card_pdf(request, pk: int):
    student = get_object_or_404(_student_queryset_for(request.user), pk=pk)
    campus = getattr(student, "campus", None)
    scoped = get_user_campus_scope(request.user)
    if scoped is not None:
        if campus is None or not user_can_access_campus(request.user, campus):
            return HttpResponseForbidden("You cannot access this student.")
    org = get_or_create_organization()
    buf = generate_student_id_card_pdf(student=student, org=org)
    response = HttpResponse(buf.read(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="student_id_{student.pk}.pdf"'
    return response


@admin_portal_required
def student_edit(request, pk: int):
    student = get_object_or_404(_student_queryset_for(request.user), pk=pk)
    scoped = get_user_campus_scope(request.user)
    current = scoped or get_current_campus(request)
    campus_qs = _campus_queryset_for(request.user)
    stream_campus = student.campus or current

    if request.method == "POST":
        if "reset_password" in request.POST:
            if not student.user_id:
                messages.error(request, "This student does not have a user account.")
                return redirect("admin_students_edit", pk=pk)
            
            if not student.email:
                messages.error(request, "This student does not have an email address.")
                return redirect("admin_students_edit", pk=pk)
            
            setup_token = PasswordSetupToken.create_for_user(student.user, created_by=request.user)
            setup_url = request.build_absolute_uri(f"/users/setup/{setup_token.token}/")
            
            send_mail(
                subject="Reset Your Student Portal Password",
                message=(
                    f"Hello {student.first_name},\n\n"
                    f"Your student number: {student.student_id}\n\n"
                    f"Click the link below to reset your password:\n{setup_url}\n\n"
                    "This link is valid for 72 hours and can only be used once.\n\n"
                    "If you did not request this, please contact your administrator."
                ),
                from_email=None,
                recipient_list=[student.email],
                fail_silently=True,
            )
            
            log_action(
                student,
                action="PASSWORD_RESET",
                description="Password reset link sent to student.",
                user=request.user,
                metadata={
                    "delivery": "email_secure_link",
                    "username": student.user.username,
                    "student_id": student.student_id,
                },
            )
            
            messages.success(request, "Password reset link sent to student's email.")
            return redirect("admin_students_edit", pk=pk)
        
        form = StudentProfileForm(request.POST, instance=student, campus=stream_campus, campus_queryset=campus_qs)
        if form.is_valid():
            obj = form.save(commit=False)
            if scoped is not None and obj.campus_id != scoped.id:
                return HttpResponseForbidden("You cannot move students outside your campus scope.")
            obj.save()
            messages.success(request, "Student updated successfully.")
            return redirect("admin_students_list")
    else:
        form = StudentProfileForm(instance=student, campus=stream_campus, campus_queryset=campus_qs)
    return render(request, "portals/admin/students/form.html", {"form": form, "mode": "edit", "student": student})
