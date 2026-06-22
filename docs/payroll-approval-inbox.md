# Payroll Approval Inbox

This feature strengthens the HR/payroll approval workflow with a role-aware approval inbox and audit-focused detail page.

## Routes

- `/admin/hr/payroll/approvals/`
- `/admin/hr/payroll/approvals/<id>/`
- `/admin/hr/payroll/approvals/<id>/action/`
- `/admin/hr/payroll/payslips/<id>/pdf/`
- `/admin/hr/payroll/payslips/<id>/mark-paid/`

## Included capabilities

- Approval dashboard grouped by pending, approved, rejected, and paid.
- Search by staff name, staff ID, and approver role.
- Approval detail with payslip summary and approval chain.
- Role validation for approval actions.
- Role aliases for school workflows:
  - Bursar: Admin or Campus Admin.
  - Headteacher: Principal.
  - Director: Admin.
- Approval and rejection comments.
- Audit notes appended to the payslip record.
- PDF download for payslip review and filing.
- Mark-as-paid action for approved payslips.
- Staff notification when a payslip becomes approved or paid.

## Existing model reuse

The rollout uses existing payroll models:

- `Payslip`
- `PayrollApproval`
- `StaffProfile`
- `PayslipAllowance`
- `PayslipDeduction`

No database schema changes are required.

## Suggested verification

Run Django checks and smoke-test:

- submit a draft payslip for approval,
- open the approval inbox,
- approve as bursar/admin or headteacher/principal,
- reject with a comment,
- confirm the approval chain shows comments and timestamps,
- download the payslip PDF,
- mark an approved payslip as paid,
- confirm staff notification is created after approval and payment.
