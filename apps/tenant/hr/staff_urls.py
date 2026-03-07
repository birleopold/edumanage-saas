from django.urls import path

from . import staff_views

urlpatterns = [
    path("payslips/", staff_views.payslip_list, name="staff_payslips_list"),
    path("payslips/<int:pk>/", staff_views.payslip_detail, name="staff_payslip_detail"),
]
