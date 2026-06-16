from django.urls import path

from . import admin_views

urlpatterns = [
    path("", admin_views.applicant_list, name="admin_admissions_applicants"),
    path("pipeline/", admin_views.applicant_pipeline, name="admin_admissions_pipeline"),
    path("leads/", admin_views.lead_list, name="admin_admissions_leads"),
    path("leads/create/", admin_views.lead_create, name="admin_admissions_lead_create"),
    path("leads/<int:pk>/edit/", admin_views.lead_edit, name="admin_admissions_lead_edit"),
    path("leads/<int:pk>/convert/", admin_views.lead_convert, name="admin_admissions_lead_convert"),
    path("forms/", admin_views.form_template_list, name="admin_admissions_form_templates"),
    path("forms/create/", admin_views.form_template_create, name="admin_admissions_form_template_create"),
    path("forms/<int:pk>/edit/", admin_views.form_template_edit, name="admin_admissions_form_template_edit"),
    path("forms/<int:pk>/fields/create/", admin_views.form_field_create, name="admin_admissions_form_field_create"),
    path("forms/fields/<int:pk>/edit/", admin_views.form_field_edit, name="admin_admissions_form_field_edit"),
    path("create/", admin_views.applicant_create, name="admin_admissions_applicant_create"),
    path("<int:pk>/admission-letter/", admin_views.applicant_admission_letter_pdf, name="admin_admissions_applicant_letter_pdf"),
    path("<int:pk>/", admin_views.applicant_detail, name="admin_admissions_applicant_detail"),
    path("<int:pk>/edit/", admin_views.applicant_edit, name="admin_admissions_applicant_edit"),
    path("<int:pk>/set-status/", admin_views.applicant_set_status, name="admin_admissions_applicant_set_status"),
    path("<int:pk>/admit/", admin_views.applicant_admit, name="admin_admissions_applicant_admit"),
    path("<int:pk>/reject/", admin_views.applicant_reject, name="admin_admissions_applicant_reject"),
    path("<int:pk>/appointments/add/", admin_views.appointment_add, name="admin_admissions_appointment_add"),
    path("appointments/<int:pk>/edit/", admin_views.appointment_edit, name="admin_admissions_appointment_edit"),
    path("<int:pk>/communications/add/", admin_views.communication_add, name="admin_admissions_communication_add"),
    path("<int:pk>/payments/add/", admin_views.payment_add, name="admin_admissions_payment_add"),
]
