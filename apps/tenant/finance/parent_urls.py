from django.urls import path

from . import parent_views

urlpatterns = [
    path("invoices/", parent_views.invoice_list, name="parent_invoices_list"),
]
