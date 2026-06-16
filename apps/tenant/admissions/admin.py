from django.contrib import admin

from .models import (
    AdmissionAppointment,
    AdmissionFormField,
    AdmissionFormTemplate,
    AdmissionLead,
    Applicant,
    ApplicantCommunication,
    ApplicantDocument,
    ApplicantPayment,
)


class ApplicantDocumentInline(admin.TabularInline):
    model = ApplicantDocument
    extra = 0
    readonly_fields = ("uploaded_at",)


class AdmissionAppointmentInline(admin.TabularInline):
    model = AdmissionAppointment
    extra = 0


class ApplicantCommunicationInline(admin.TabularInline):
    model = ApplicantCommunication
    extra = 0
    readonly_fields = ("created_at",)


class ApplicantPaymentInline(admin.TabularInline):
    model = ApplicantPayment
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Applicant)
class ApplicantAdmin(admin.ModelAdmin):
    list_display = (
        "application_reference",
        "full_name",
        "phone",
        "campus",
        "status",
        "source",
        "submitted_online",
        "created_student",
        "created_admission_invoice",
        "created_at",
    )
    list_filter = ("status", "source", "submitted_online", "campus", "created_at")
    search_fields = ("application_reference", "first_name", "last_name", "email", "phone", "guardian_name")
    readonly_fields = ("application_reference", "created_at", "updated_at")
    date_hierarchy = "created_at"
    inlines = (ApplicantDocumentInline, AdmissionAppointmentInline, ApplicantCommunicationInline, ApplicantPaymentInline)


@admin.register(ApplicantDocument)
class ApplicantDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "applicant", "uploaded_at")
    search_fields = ("title", "applicant__application_reference", "applicant__first_name", "applicant__last_name")
    readonly_fields = ("uuid", "uploaded_at")
    date_hierarchy = "uploaded_at"


@admin.register(AdmissionLead)
class AdmissionLeadAdmin(admin.ModelAdmin):
    list_display = ("learner_name", "parent_name", "phone", "source", "status", "follow_up_at", "converted_applicant", "created_at")
    list_filter = ("status", "source", "campus", "created_at")
    search_fields = ("learner_name", "parent_name", "email", "phone")


class AdmissionFormFieldInline(admin.TabularInline):
    model = AdmissionFormField
    extra = 1


@admin.register(AdmissionFormTemplate)
class AdmissionFormTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "campus", "program", "class_group", "is_default", "is_active", "admission_fee_item", "admission_fee_amount")
    list_filter = ("is_active", "is_default", "campus", "program", "class_group")
    inlines = (AdmissionFormFieldInline,)


@admin.register(AdmissionAppointment)
class AdmissionAppointmentAdmin(admin.ModelAdmin):
    list_display = ("applicant", "appointment_type", "status", "scheduled_at", "assigned_to", "score")
    list_filter = ("appointment_type", "status", "scheduled_at")
    search_fields = ("applicant__application_reference", "applicant__first_name", "applicant__last_name")


@admin.register(ApplicantCommunication)
class ApplicantCommunicationAdmin(admin.ModelAdmin):
    list_display = ("applicant", "channel", "direction", "subject", "logged_by", "created_at")
    list_filter = ("channel", "direction", "created_at")
    search_fields = ("applicant__application_reference", "subject", "message")


@admin.register(ApplicantPayment)
class ApplicantPaymentAdmin(admin.ModelAdmin):
    list_display = ("applicant", "amount", "method", "status", "reference", "received_at")
    list_filter = ("method", "status", "received_at")
    search_fields = ("applicant__application_reference", "reference")
