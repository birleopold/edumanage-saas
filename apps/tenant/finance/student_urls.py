from django.urls import path

from . import student_views

urlpatterns = [
    path("invoices/", student_views.invoice_list, name="student_invoices_list"),
    path(
        "invoices/<int:pk>/payments/<int:payment_id>/receipt/",
        student_views.payment_receipt_pdf,
        name="student_payment_receipt_pdf",
    ),
    path("invoices/<int:pk>/print/", student_views.invoice_print, name="student_invoices_print"),
    path("invoices/<int:pk>/", student_views.invoice_detail, name="student_invoices_detail"),
]
