from django.urls import path

from . import admin_views

urlpatterns = [
    path("fee-items/", admin_views.fee_item_list, name="admin_fee_items_list"),
    path("fee-items/create/", admin_views.fee_item_create, name="admin_fee_items_create"),
    path("fee-items/<int:pk>/edit/", admin_views.fee_item_edit, name="admin_fee_items_edit"),

    path("invoices/", admin_views.invoice_list, name="admin_invoices_list"),
    path("invoices/create/", admin_views.invoice_create, name="admin_invoices_create"),
    path("invoices/<int:pk>/edit/", admin_views.invoice_edit, name="admin_invoices_edit"),
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
