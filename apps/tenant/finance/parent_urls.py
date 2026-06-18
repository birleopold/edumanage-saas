from django.urls import path

from . import parent_views

urlpatterns = [
    path("invoices/", parent_views.invoice_list, name="parent_invoices_list"),
    path("invoices/<int:pk>/pay/", parent_views.initiate_payment, name="parent_invoice_pay"),
    path(
        "invoices/<int:pk>/payments/<int:payment_id>/receipt/",
        parent_views.payment_receipt_pdf,
        name="parent_payment_receipt_pdf",
    ),
    path("invoices/<int:pk>/print/", parent_views.invoice_print, name="parent_invoices_print"),
    path("invoices/<int:pk>/", parent_views.invoice_detail, name="parent_invoices_detail"),
]
