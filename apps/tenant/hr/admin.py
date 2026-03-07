from django.contrib import admin

from .models import (
    AllowanceType,
    DeductionType,
    Department,
    DepartmentHead,
    PayGrade,
    Payslip,
    PayslipAllowance,
    PayslipDeduction,
    PayrollApproval,
    Position,
    SalaryStructure,
    StaffProfile,
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "campus", "is_active")
    list_filter = ("is_active", "campus")
    search_fields = ("name", "code")


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("title", "department", "is_active")
    list_filter = ("is_active", "department")
    search_fields = ("title",)


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ("staff_id", "first_name", "last_name", "department", "position", "is_active")
    list_filter = ("is_active", "staff_category", "department", "campus")
    search_fields = ("staff_id", "first_name", "last_name", "email", "phone")


@admin.register(DepartmentHead)
class DepartmentHeadAdmin(admin.ModelAdmin):
    list_display = ("department", "staff", "start_date", "end_date", "is_active")
    list_filter = ("is_active",)
    search_fields = ("department__name", "staff__first_name", "staff__last_name")


@admin.register(PayGrade)
class PayGradeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "min_salary", "max_salary", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")


@admin.register(SalaryStructure)
class SalaryStructureAdmin(admin.ModelAdmin):
    list_display = ("staff", "pay_grade", "base_salary", "effective_date", "is_active")
    list_filter = ("is_active", "pay_grade")
    search_fields = ("staff__first_name", "staff__last_name", "staff__staff_id")


@admin.register(AllowanceType)
class AllowanceTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_taxable", "is_active")
    list_filter = ("is_active", "is_taxable")
    search_fields = ("name", "code")


@admin.register(DeductionType)
class DeductionTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_percentage", "default_rate", "is_active")
    list_filter = ("is_active", "is_percentage")
    search_fields = ("name", "code")


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ("staff", "period_year", "period_month", "net_salary", "status", "generated_at")
    list_filter = ("status", "period_year", "period_month")
    search_fields = ("staff__first_name", "staff__last_name", "staff__staff_id")
    readonly_fields = ("generated_at", "approved_at", "paid_at")


@admin.register(PayslipAllowance)
class PayslipAllowanceAdmin(admin.ModelAdmin):
    list_display = ("payslip", "allowance_type", "amount")
    search_fields = ("payslip__staff__first_name", "payslip__staff__last_name")


@admin.register(PayslipDeduction)
class PayslipDeductionAdmin(admin.ModelAdmin):
    list_display = ("payslip", "deduction_type", "amount")
    search_fields = ("payslip__staff__first_name", "payslip__staff__last_name")


@admin.register(PayrollApproval)
class PayrollApprovalAdmin(admin.ModelAdmin):
    list_display = ("payslip", "approver_role", "approver", "status", "approved_at")
    list_filter = ("status", "approver_role")
    search_fields = ("payslip__staff__first_name", "payslip__staff__last_name")
