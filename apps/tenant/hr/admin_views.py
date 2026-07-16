from typing import Optional

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_current_campus, get_or_create_organization
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required
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


def _campus_queryset(user=None):
    org = get_or_create_organization()
    qs = Campus.objects.filter(organization=org).order_by("name")
    scoped = get_user_campus_scope(user) if user is not None else None
    if scoped:
        qs = qs.filter(pk=scoped.pk)
    return qs


def _selected_campus_id(request) -> Optional[int]:
    scoped = get_user_campus_scope(request.user)
    if scoped:
        return scoped.pk
    current = get_current_campus(request)
    if "campus" in request.GET:
        campus_filter = request.GET.get("campus")
        if campus_filter == "":
            return None
        try:
            return int(campus_filter)
        except (TypeError, ValueError):
            return None
    return current.id if current else None


def _staff_queryset_for(user):
    qs = StaffProfile.objects.select_related("campus", "department", "position", "user")
    scoped = get_user_campus_scope(user)
    if scoped:
        qs = qs.filter(campus=scoped)
    return qs


def _department_queryset_for(user):
    qs = Department.objects.select_related("campus")
    scoped = get_user_campus_scope(user)
    if scoped:
        qs = qs.filter(Q(campus=scoped) | Q(campus__isnull=True))
    return qs


def _editable_department_queryset_for(user):
    qs = Department.objects.select_related("campus")
    scoped = get_user_campus_scope(user)
    if scoped:
        qs = qs.filter(campus=scoped)
    return qs


def _position_queryset_for(user):
    qs = Position.objects.select_related("department", "department__campus")
    scoped = get_user_campus_scope(user)
    if scoped:
        qs = qs.filter(Q(department__campus=scoped) | Q(department__campus__isnull=True))
    return qs


def _department_head_queryset_for(user):
    qs = _department_head_base_queryset()
    scoped = get_user_campus_scope(user)
    if scoped:
        qs = qs.filter(department__campus=scoped, staff__campus=scoped)
    return qs


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


@admin_portal_required
def staff_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    campuses = _campus_queryset(request.user)
    campus_id = _selected_campus_id(request)

    qs = _staff_queryset_for(request.user)

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

    qs = _department_head_queryset_for(request.user)
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

    departments = _editable_department_queryset_for(request.user)
    staff_queryset = _staff_queryset_for(request.user)
    if request.method == "POST":
        form = DepartmentHeadForm(request.POST, departments=departments, staff_queryset=staff_queryset)
        if form.is_valid():
            form.save()
            messages.success(request, "Department head assigned.")
            return redirect("admin_hr_department_heads_list")
    else:
        form = DepartmentHeadForm(departments=departments, staff_queryset=staff_queryset)

    return render(request, "portals/admin/hr/department_head_form.html", {"form": form, "mode": "create"})


def department_head_edit(request, pk: int):
    if not _admin_or_principal_required(request):
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("Forbidden")

    departments = _editable_department_queryset_for(request.user)
    staff_queryset = _staff_queryset_for(request.user)
    obj = get_object_or_404(_department_head_queryset_for(request.user), pk=pk)
    if request.method == "POST":
        form = DepartmentHeadForm(request.POST, instance=obj, departments=departments, staff_queryset=staff_queryset)
        if form.is_valid():
            form.save()
            messages.success(request, "Department head updated.")
            return redirect("admin_hr_department_heads_list")
    else:
        form = DepartmentHeadForm(instance=obj, departments=departments, staff_queryset=staff_queryset)

    return render(
        request,
        "portals/admin/hr/department_head_form.html",
        {"form": form, "mode": "edit", "head": obj},
    )


@admin_portal_required
def staff_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    campuses = _campus_queryset(request.user)
    campus_id = _selected_campus_id(request)

    qs = _staff_queryset_for(request.user)

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


@admin_portal_required
def staff_create(request):
    campuses = _campus_queryset(request.user)
    departments = _department_queryset_for(request.user)
    staff_queryset = _staff_queryset_for(request.user)
    scoped = get_user_campus_scope(request.user)
    current = scoped or get_current_campus(request)

    if request.method == "POST":
        form = StaffProfileForm(request.POST, campuses=campuses, departments=departments, staff_queryset=staff_queryset)
        if form.is_valid():
            with transaction.atomic():
                staff = form.save(commit=False)
                if scoped:
                    staff.campus = scoped
                elif staff.campus_id is None and current is not None:
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
        form = StaffProfileForm(campuses=campuses, departments=departments, staff_queryset=staff_queryset)
        if current is not None:
            form.fields["campus"].initial = current

    return render(request, "portals/admin/hr/staff_form.html", {"form": form, "mode": "create", "campuses": campuses})


@admin_portal_required
def staff_edit(request, pk: int):
    campuses = _campus_queryset(request.user)
    departments = _department_queryset_for(request.user)
    staff_queryset = _staff_queryset_for(request.user).exclude(pk=pk)
    scoped = get_user_campus_scope(request.user)
    staff = get_object_or_404(_staff_queryset_for(request.user), pk=pk)

    if request.method == "POST":
        form = StaffProfileForm(request.POST, instance=staff, campuses=campuses, departments=departments, staff_queryset=staff_queryset)
        if form.is_valid():
            staff = form.save(commit=False)
            if scoped:
                staff.campus = scoped
            staff.save()
            messages.success(request, "Staff member updated.")
            return redirect("admin_hr_staff_detail", pk=staff.pk)
    else:
        form = StaffProfileForm(instance=staff, campuses=campuses, departments=departments, staff_queryset=staff_queryset)

    return render(
        request,
        "portals/admin/hr/staff_form.html",
        {"form": form, "mode": "edit", "staff": staff},
    )


@admin_portal_required
def staff_detail(request, pk: int):
    staff = get_object_or_404(_staff_queryset_for(request.user), pk=pk)
    return render(request, "portals/admin/hr/staff_detail.html", {"staff": staff})


@admin_portal_required
def department_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = _department_queryset_for(request.user)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/hr/departments_list.html",
        {"departments": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@admin_portal_required
def department_create(request):
    campuses = _campus_queryset(request.user)
    scoped = get_user_campus_scope(request.user)
    current = scoped or get_current_campus(request)

    if request.method == "POST":
        form = DepartmentForm(request.POST, campuses=campuses)
        if form.is_valid():
            dept = form.save(commit=False)
            if scoped:
                dept.campus = scoped
            elif dept.campus_id is None and current is not None:
                dept.campus = current
            dept.save()
            messages.success(request, "Department created.")
            return redirect("admin_hr_departments_list")
    else:
        form = DepartmentForm(campuses=campuses)
        if current is not None:
            form.fields["campus"].initial = current

    return render(request, "portals/admin/hr/department_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def department_edit(request, pk: int):
    campuses = _campus_queryset(request.user)
    scoped = get_user_campus_scope(request.user)
    dept = get_object_or_404(_editable_department_queryset_for(request.user), pk=pk)

    if request.method == "POST":
        form = DepartmentForm(request.POST, instance=dept, campuses=campuses)
        if form.is_valid():
            dept = form.save(commit=False)
            if scoped:
                dept.campus = scoped
            dept.save()
            messages.success(request, "Department updated.")
            return redirect("admin_hr_departments_list")
    else:
        form = DepartmentForm(instance=dept, campuses=campuses)

    return render(
        request,
        "portals/admin/hr/department_form.html",
        {"form": form, "mode": "edit", "department": dept},
    )


@admin_portal_required
def position_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = _position_queryset_for(request.user)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(department__name__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/hr/positions_list.html",
        {"positions": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@admin_portal_required
def position_create(request):
    departments = _department_queryset_for(request.user)
    if request.method == "POST":
        form = PositionForm(request.POST, departments=departments)
        if form.is_valid():
            form.save()
            messages.success(request, "Position created.")
            return redirect("admin_hr_positions_list")
    else:
        form = PositionForm(departments=departments)

    return render(request, "portals/admin/hr/position_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def position_edit(request, pk: int):
    departments = _department_queryset_for(request.user)
    position = get_object_or_404(_position_queryset_for(request.user), pk=pk)

    if request.method == "POST":
        form = PositionForm(request.POST, instance=position, departments=departments)
        if form.is_valid():
            form.save()
            messages.success(request, "Position updated.")
            return redirect("admin_hr_positions_list")
    else:
        form = PositionForm(instance=position, departments=departments)

    return render(
        request,
        "portals/admin/hr/position_form.html",
        {"form": form, "mode": "edit", "position": position},
    )
