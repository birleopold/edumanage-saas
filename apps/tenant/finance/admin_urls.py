from django.urls import include, path

from . import admin_views, bulk_views, communication_views, dashboard_views

urlpatterns = [
    path("", dashboard_views.finance_dashboard, name="admin_finance_dashboard"),
    path("books/", include("apps.tenant.finance.books")),
    path(
        "payments/<int:pk>/receipt/",
        admin_views.payment_receipt_pdf,
        name="admin_payment_receipt_pdf",
    ),
    path("fee-items/", admin_views.fee_item_list, name="admin_fee_items_list"),
    path("fee-items/create/", admin_views.fee_item_create, name="admin_fee_items_create"),
    path("fee-items/<int:pk>/edit/", admin_views.fee_item_edit, name="admin_fee_items_edit"),
    path("messaging-report/", admin_views.messaging_report, name="admin_finance_messaging_report"),
    path("message-logs/", admin_views.message_logs_list, name="admin_finance_message_logs"),
    path("communication-ops/", communication_views.communication_operations, name="admin_finance_communication_operations"),

    path("invoices/", admin_views.invoice_list, name="admin_invoices_list"),
    path("invoices/create/", admin_views.invoice_create, name="admin_invoices_create"),
    path("invoices/bulk-create/", bulk_views.invoice_bulk_create, name="admin_invoices_bulk_create"),
    path("invoices/export/csv/", admin_views.invoice_export_csv, name="admin_invoices_export_csv"),
    path(
        "invoices/<int:pk>/carry-forward/",
        admin_views.invoice_carry_forward,
        name="admin_invoices_carry_forward",
    ),
    path(
        "invoices/<int:pk>/clone/",
        admin_views.invoice_clone,
        name="admin_invoices_clone",
    ),
    path("invoices/<int:pk>/edit/", admin_views.invoice_edit, name="admin_invoices_edit"),
    path("invoices/<int:pk>/print/", admin_views.invoice_print, name="admin_invoices_print"),
    path("invoices/<int:pk>/", admin_views.invoice_detail, name="admin_invoices_detail"),
    path(
        "invoices/<int:pk>/lines/<int:line_id>/remove/",
        admin_views.invoice_line_remove,
        name="admin_invoices_line_remove",
    ),
    path(
        "invoices/<int:pk>/payments/<int:payment_id>/remove/",
        admin_views.invoice_payment_remove,
        name="admin_invoices_payment_remove",
    ),
]
