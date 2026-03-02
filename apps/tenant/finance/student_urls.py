from django.urls import path

from . import student_views

urlpatterns = [
    path("invoices/", student_views.invoice_list, name="student_invoices_list"),
    path("invoices/<int:pk>/", student_views.invoice_detail, name="student_invoices_detail"),
]
