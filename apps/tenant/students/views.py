from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from django.contrib import messages

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_current_campus, get_or_create_organization
from apps.tenant.orgsettings.utils import log_action
from apps.tenant.users.models import Role, User, PasswordSetupToken
from apps.tenant.portals.permissions import role_required

from .forms import StudentProfileForm
from .models import StudentProfile
from .services import generate_next_student_id


def _campus_queryset():
    org = get_or_create_organization()
    return Campus.objects.filter(organization=org).order_by("name")


@role_required(Role.ADMIN)
def student_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page_raw = request.GET.get("per_page")
    page_number = request.GET.get("page") or 1

    campuses = _campus_queryset()
    current = get_current_campus(request)

    if "campus" in request.GET:
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

    students_qs = StudentProfile.objects.all()
    if campus_id:
        students_qs = students_qs.filter(campus_id=campus_id)
    if q:
        students_qs = students_qs.filter(
            Q(student_id__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
        )

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


@role_required(Role.ADMIN)
def student_create(request):
    current = get_current_campus(request)
    if request.method == "POST":
        form = StudentProfileForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                if obj.campus_id is None and current is not None:
                    obj.campus = current

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
        form = StudentProfileForm()
        if current is not None:
            form.fields["campus"].initial = current
    return render(request, "portals/admin/students/form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def student_credentials(request, pk: int):
    student = get_object_or_404(StudentProfile, pk=pk)
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


@role_required(Role.ADMIN)
def student_edit(request, pk: int):
    student = get_object_or_404(StudentProfile, pk=pk)
    
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
        
        form = StudentProfileForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            messages.success(request, "Student updated successfully.")
            return redirect("admin_students_list")
    else:
        form = StudentProfileForm(instance=student)
    return render(request, "portals/admin/students/form.html", {"form": form, "mode": "edit", "student": student})
