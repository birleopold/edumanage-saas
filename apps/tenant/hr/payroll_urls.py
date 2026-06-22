from django.urls import path

from . import payroll_admin_views, payroll_approval_views

urlpatterns = [
    # Pay Grades
    path("pay-grades/", payroll_admin_views.pay_grade_list, name="admin_hr_payroll_pay_grades_list"),
    path("pay-grades/create/", payroll_admin_views.pay_grade_create, name="admin_hr_payroll_pay_grade_create"),
    path("pay-grades/<int:pk>/edit/", payroll_admin_views.pay_grade_edit, name="admin_hr_payroll_pay_grade_edit"),
    # Salary Structures
    path("salary-structures/", payroll_admin_views.salary_structure_list, name="admin_hr_payroll_salary_structures_list"),
    path("salary-structures/create/", payroll_admin_views.salary_structure_create, name="admin_hr_payroll_salary_structure_create"),
    path("salary-structures/<int:pk>/edit/", payroll_admin_views.salary_structure_edit, name="admin_hr_payroll_salary_structure_edit"),
    # Allowance Types
    path("allowance-types/", payroll_admin_views.allowance_type_list, name="admin_hr_payroll_allowance_types_list"),
    path("allowance-types/create/", payroll_admin_views.allowance_type_create, name="admin_hr_payroll_allowance_type_create"),
    path("allowance-types/<int:pk>/edit/", payroll_admin_views.allowance_type_edit, name="admin_hr_payroll_allowance_type_edit"),
    # Deduction Types
    path("deduction-types/", payroll_admin_views.deduction_type_list, name="admin_hr_payroll_deduction_types_list"),
    path("deduction-types/create/", payroll_admin_views.deduction_type_create, name="admin_hr_payroll_deduction_type_create"),
    path("deduction-types/<int:pk>/edit/", payroll_admin_views.deduction_type_edit, name="admin_hr_payroll_deduction_type_edit"),
    # Approval Inbox
    path("approvals/", payroll_approval_views.approval_dashboard, name="admin_hr_payroll_approval_dashboard"),
    path("approvals/<int:pk>/", payroll_approval_views.approval_detail, name="admin_hr_payroll_approval_detail"),
    path("approvals/<int:pk>/action/", payroll_approval_views.approval_action, name="admin_hr_payroll_approval_action"),
    # Payslips
    path("payslips/", payroll_admin_views.payslip_list, name="admin_hr_payroll_payslips_list"),
    path("payslips/generate/", payroll_admin_views.payslip_generate, name="admin_hr_payroll_payslip_generate"),
    path("payslips/<int:pk>/", payroll_admin_views.payslip_detail, name="admin_hr_payroll_payslip_detail"),
    path("payslips/<int:pk>/pdf/", payroll_approval_views.payslip_pdf, name="admin_hr_payroll_payslip_pdf"),
    path("payslips/<int:pk>/submit/", payroll_admin_views.payslip_submit_for_approval, name="admin_hr_payroll_payslip_submit"),
    path("payslips/<int:pk>/approve/", payroll_admin_views.payslip_approve, name="admin_hr_payroll_payslip_approve"),
    path("payslips/<int:pk>/mark-paid/", payroll_approval_views.mark_paid, name="admin_hr_payroll_payslip_mark_paid"),
]
