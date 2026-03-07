from typing import Optional

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_current_campus, get_or_create_organization
from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role, User

from .forms import DepartmentForm, DepartmentHeadForm, PositionForm, StaffProfileForm
from .models import Department, DepartmentHead, Position, StaffProfile
from .payroll_forms import (
    AllowanceTypeForm,
    DeductionTypeForm,
    PayGradeForm,
    PayslipApprovalForm,
    PayslipGenerateForm,
    SalaryStructureForm,
)
from .payroll_models import AllowanceType, DeductionType, PayGrade, Payslip, SalaryStructure


def _admin_or_principal_required(request):
    if not request.user.is_authenticated:
        return False
    return request.user.has_role(Role.ADMIN) or request.user.has_role(Role.PRINCIPAL)


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


def _generate_unique_username(base: str) -> str:
    base = (base or "staff").strip()
    if not base:
        base = "staff"

    username = base
    i = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{i}"
        i += 1
    return username


def _create_staff_user(username: str, email: str, role_code: str) -> User:
    username = _generate_unique_username(username)
    user = User.objects.create(username=username, email=email or "")
    user.set_unusable_password()
    user.save(update_fields=["password"])

    if role_code:
        role = Role.objects.filter(code=role_code).first()
        if role:
            user.roles.add(role)

    return user


@role_required(Role.ADMIN)
def staff_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
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

    qs = StaffProfile.objects.select_related("campus", "department", "position", "user").all()

    if campus_id:
        qs = qs.filter(campus_id=campus_id)

    if q:
        qs = qs.filter(
            Q(staff_id__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(phone__icontains=q)
            | Q(email__icontains=q)
        )


def _department_head_base_queryset():
    return DepartmentHead.objects.select_related(
        "department",
        "department__campus",
        "staff",
        "staff__campus",
    ).all()


def department_head_list(request):
    if not _admin_or_principal_required(request):
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("Forbidden")

    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = _department_head_base_queryset()
    if q:
        qs = qs.filter(
            Q(department__name__icontains=q)
            | Q(staff__first_name__icontains=q)
            | Q(staff__last_name__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/hr/department_heads_list.html",
        {"heads": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


def department_head_create(request):
    if not _admin_or_principal_required(request):
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("Forbidden")

    if request.method == "POST":
        form = DepartmentHeadForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Department head assigned.")
            return redirect("admin_hr_department_heads_list")
    else:
        form = DepartmentHeadForm()

    return render(request, "portals/admin/hr/department_head_form.html", {"form": form, "mode": "create"})


def department_head_edit(request, pk: int):
    if not _admin_or_principal_required(request):
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("Forbidden")

    obj = get_object_or_404(DepartmentHead, pk=pk)
    if request.method == "POST":
        form = DepartmentHeadForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Department head updated.")
            return redirect("admin_hr_department_heads_list")
    else:
        form = DepartmentHeadForm(instance=obj)

    return render(
        request,
        "portals/admin/hr/department_head_form.html",
        {"form": form, "mode": "edit", "head": obj},
    )


@role_required(Role.ADMIN)
def staff_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
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

    qs = StaffProfile.objects.select_related("campus", "department", "position", "user").all()

    if campus_id:
        qs = qs.filter(campus_id=campus_id)

    if q:
        qs = qs.filter(
            Q(staff_id__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(phone__icontains=q)
            | Q(email__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/hr/staff_list.html",
        {
            "staff": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "campuses": campuses,
            "selected_campus_id": campus_id,
        },
    )


@role_required(Role.ADMIN)
def staff_create(request):
    campuses = _campus_queryset()
    current = get_current_campus(request)

    if request.method == "POST":
        form = StaffProfileForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                staff = form.save(commit=False)
                if staff.campus_id is None and current is not None:
                    staff.campus = current

                create_user = form.cleaned_data.get("create_user")
                if create_user and staff.user_id is None:
                    username = form.cleaned_data.get("username") or (staff.email.split("@")[0] if staff.email else "staff")
                    role_code = form.cleaned_data.get("role_code") or Role.TEACHER
                    staff.user = _create_staff_user(username=username, email=staff.email, role_code=role_code)

                staff.save()

            messages.success(request, "Staff member created.")
            return redirect("admin_hr_staff_list")
    else:
        form = StaffProfileForm()
        if current is not None:
            form.fields["campus"].initial = current

    return render(request, "portals/admin/hr/staff_form.html", {"form": form, "mode": "create", "campuses": campuses})


@role_required(Role.ADMIN)
def staff_edit(request, pk: int):
    staff = get_object_or_404(StaffProfile, pk=pk)

    if request.method == "POST":
        form = StaffProfileForm(request.POST, instance=staff)
        if form.is_valid():
            form.save()
            messages.success(request, "Staff member updated.")
            return redirect("admin_hr_staff_detail", pk=staff.pk)
    else:
        form = StaffProfileForm(instance=staff)

    return render(
        request,
        "portals/admin/hr/staff_form.html",
        {"form": form, "mode": "edit", "staff": staff},
    )


@role_required(Role.ADMIN)
def staff_detail(request, pk: int):
    staff = get_object_or_404(StaffProfile.objects.select_related("campus", "department", "position", "user"), pk=pk)
    return render(request, "portals/admin/hr/staff_detail.html", {"staff": staff})


@role_required(Role.ADMIN)
def department_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Department.objects.select_related("campus").all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/hr/departments_list.html",
        {"departments": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.ADMIN)
def department_create(request):
    current = get_current_campus(request)

    if request.method == "POST":
        form = DepartmentForm(request.POST)
        if form.is_valid():
            dept = form.save(commit=False)
            if dept.campus_id is None and current is not None:
                dept.campus = current
            dept.save()
            messages.success(request, "Department created.")
            return redirect("admin_hr_departments_list")
    else:
        form = DepartmentForm()
        if current is not None:
            form.fields["campus"].initial = current

    return render(request, "portals/admin/hr/department_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def department_edit(request, pk: int):
    dept = get_object_or_404(Department, pk=pk)

    if request.method == "POST":
        form = DepartmentForm(request.POST, instance=dept)
        if form.is_valid():
            form.save()
            messages.success(request, "Department updated.")
            return redirect("admin_hr_departments_list")
    else:
        form = DepartmentForm(instance=dept)

    return render(
        request,
        "portals/admin/hr/department_form.html",
        {"form": form, "mode": "edit", "department": dept},
    )


@role_required(Role.ADMIN)
def position_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = Position.objects.select_related("department", "department__campus").all()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(department__name__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/hr/positions_list.html",
        {"positions": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@role_required(Role.ADMIN)
def position_create(request):
    if request.method == "POST":
        form = PositionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Position created.")
            return redirect("admin_hr_positions_list")
    else:
        form = PositionForm()

    return render(request, "portals/admin/hr/position_form.html", {"form": form, "mode": "create"})


@role_required(Role.ADMIN)
def position_edit(request, pk: int):
    position = get_object_or_404(Position, pk=pk)

    if request.method == "POST":
        form = PositionForm(request.POST, instance=position)
        if form.is_valid():
            form.save()
            messages.success(request, "Position updated.")
            return redirect("admin_hr_positions_list")
    else:
        form = PositionForm(instance=position)

    return render(
        request,
        "portals/admin/hr/position_form.html",
        {"form": form, "mode": "edit", "position": position},
    )
