from typing import Optional

from django.contrib import messages
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_current_campus, get_or_create_organization
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.students.models import StudentProfile
from apps.tenant.students.services import generate_next_student_id
from apps.tenant.users.models import Role, User
from apps.tenant.orgsettings.utils import log_action

from .forms import ApplicantForm
from .models import Applicant
from .pdf_letter import generate_admission_letter_pdf


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = request.GET.get("per_page")
    per_page = default
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = default
    return max(1, min(per_page, max_value))


def _campus_queryset():
    org = get_or_create_organization()
    return Campus.objects.filter(organization=org).order_by("name")


def _ensure_student_role():
    return Role.objects.get_or_create(code=Role.STUDENT, defaults={"name": "Student"})[0]


def _generate_unique_username(base: str) -> str:
    base = (base or "student").strip()
    if not base:
        base = "student"

    username = base
    i = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{i}"
        i += 1
    return username


def _create_student_user(applicant: Applicant) -> User:
    if applicant.email:
        base = applicant.email.split("@")[0]
    else:
        base = f"student{applicant.id}"

    username = _generate_unique_username(base)
    user = User.objects.create(username=username, email=applicant.email)
    user.set_unusable_password()
    user.save(update_fields=["password"])

    student_role = _ensure_student_role()
    user.roles.add(student_role)

    return user


@admin_portal_required
def applicant_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Applicant.objects.select_related(
        "campus",
        "target_term",
        "target_term__year",
        "target_level",
        "target_program",
        "target_class_group",
        "created_student",
    ).all()

    if q:
        qs = qs.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(email__icontains=q)
            | Q(phone__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/admissions/applicants_list.html",
        {"applicants": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@admin_portal_required
def applicant_create(request):
    campuses = _campus_queryset()
    current = get_current_campus(request)

    if request.method == "POST":
        form = ApplicantForm(request.POST, campuses=campuses)
        if form.is_valid():
            applicant = form.save(commit=False)
            if applicant.campus_id is None and current is not None:
                applicant.campus = current
            applicant.save()
            messages.success(request, "Applicant created.")
            return redirect("admin_admissions_applicants")
    else:
        form = ApplicantForm(campuses=campuses)
        if current is not None:
            form.fields["campus"].initial = current

    return render(request, "portals/admin/admissions/applicant_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def applicant_edit(request, pk: int):
    campuses = _campus_queryset()
    applicant = get_object_or_404(Applicant, pk=pk)

    if request.method == "POST":
        form = ApplicantForm(request.POST, instance=applicant, campuses=campuses)
        if form.is_valid():
            form.save()
            messages.success(request, "Applicant updated.")
            return redirect("admin_admissions_applicant_detail", pk=applicant.pk)
    else:
        form = ApplicantForm(instance=applicant, campuses=campuses)

    return render(
        request,
        "portals/admin/admissions/applicant_form.html",
        {"form": form, "mode": "edit", "applicant": applicant},
    )


@admin_portal_required
def applicant_detail(request, pk: int):
    applicant = get_object_or_404(
        Applicant.objects.select_related(
            "campus",
            "target_term",
            "target_term__year",
            "target_level",
            "target_program",
            "target_class_group",
            "created_student",
        ),
        pk=pk,
    )
    return render(request, "portals/admin/admissions/applicant_detail.html", {"applicant": applicant})


@admin_portal_required
def applicant_set_status(request, pk: int):
    applicant = get_object_or_404(Applicant, pk=pk)
    status = (request.POST.get("status") or "").strip()

    allowed = {Applicant.NEW, Applicant.IN_REVIEW, Applicant.REJECTED}
    if status not in allowed:
        messages.error(request, "Invalid status.")
        return redirect("admin_admissions_applicant_detail", pk=applicant.pk)

    applicant.status = status
    applicant.save(update_fields=["status", "updated_at"])
    messages.success(request, "Status updated.")
    return redirect("admin_admissions_applicant_detail", pk=applicant.pk)


@admin_portal_required
def applicant_reject(request, pk: int):
    applicant = get_object_or_404(Applicant, pk=pk)
    applicant.status = Applicant.REJECTED
    applicant.save(update_fields=["status", "updated_at"])
    messages.success(request, "Applicant rejected.")
    return redirect("admin_admissions_applicant_detail", pk=applicant.pk)


@admin_portal_required
def applicant_admit(request, pk: int):
    applicant = get_object_or_404(Applicant, pk=pk)

    current = get_current_campus(request)

    if applicant.status == Applicant.ADMITTED and applicant.created_student_id:
        messages.info(request, "Applicant already admitted.")
        return redirect("admin_admissions_applicant_detail", pk=applicant.pk)

    with transaction.atomic():
        campus = applicant.campus or current
        student_id = generate_next_student_id(campus)

        user: Optional[User] = None
        temp_password: Optional[str] = None
        if applicant.email:
            temp_password = User.objects.make_random_password(length=12)
            user = User.objects.create(username=student_id, email=applicant.email)
            user.set_password(temp_password)
            user.must_change_password = True
            user.save(update_fields=["password", "must_change_password"])

            student_role = _ensure_student_role()
            user.roles.add(student_role)

        student = StudentProfile.objects.create(
            user=user,
            campus=campus,
            first_name=applicant.first_name,
            last_name=applicant.last_name,
            date_of_birth=applicant.date_of_birth,
            student_id=student_id,
            email=applicant.email or "",
            is_active=True,
        )

        applicant.status = Applicant.ADMITTED
        applicant.created_student = student
        applicant.save(update_fields=["status", "created_student", "updated_at"])

    if applicant.email and temp_password:
        send_mail(
            subject="Your Student Portal Login",
            message=(
                f"Hello {student.first_name},\n\n"
                f"Your student number: {student.student_id}\n"
                f"Temporary password: {temp_password}\n\n"
                "Please change your password immediately after your first login."
            ),
            from_email=None,
            recipient_list=[applicant.email],
            fail_silently=True,
        )
        log_action(
            student,
            action="CREDENTIALS_ISSUED",
            description="Student credentials issued via email (admissions admit).",
            user=request.user,
            metadata={
                "delivery": "email",
                "username": student.user.username if student.user_id else "",
                "student_id": student.student_id,
            },
        )
        messages.success(request, "Applicant admitted. Login details sent via email.")
    else:
        messages.success(request, "Applicant admitted and student profile created.")
    return redirect("admin_admissions_applicant_detail", pk=applicant.pk)


@admin_portal_required
def applicant_admission_letter_pdf(request, pk: int):
    applicant = get_object_or_404(
        Applicant.objects.select_related("created_student", "campus", "target_term"),
        pk=pk,
    )
    if applicant.status != Applicant.ADMITTED or not applicant.created_student_id:
        return HttpResponseForbidden(
            "This letter is only available after admission, once a student record exists."
        )
    student = applicant.created_student
    org = get_or_create_organization()
    buf = generate_admission_letter_pdf(
        applicant=applicant,
        student=student,
        org=org,
        issued_by=request.user.get_full_name() or request.user.get_username(),
    )
    log_action(
        applicant,
        action="ADMISSION_LETTER_PDF",
        description=f"Admission letter PDF generated for student {student.student_id}.",
        user=request.user,
        metadata={"student_profile_id": student.pk},
    )
    response = HttpResponse(buf.read(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="admission_{applicant.pk}.pdf"'
    return response
