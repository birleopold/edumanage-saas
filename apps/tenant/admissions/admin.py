from django.contrib import admin

from .models import Applicant, ApplicantDocument


class ApplicantDocumentInline(admin.TabularInline):
    model = ApplicantDocument
    extra = 0
    readonly_fields = ("uploaded_at",)


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
        "created_at",
    )
    list_filter = ("status", "source", "submitted_online", "campus", "created_at")
    search_fields = (
        "application_reference",
        "first_name",
        "last_name",
        "email",
        "phone",
        "guardian_name",
    )
    readonly_fields = ("application_reference", "created_at", "updated_at")
    date_hierarchy = "created_at"
    inlines = (ApplicantDocumentInline,)


@admin.register(ApplicantDocument)
class ApplicantDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "applicant", "uploaded_at")
    search_fields = ("title", "applicant__application_reference", "applicant__first_name", "applicant__last_name")
    readonly_fields = ("uuid", "uploaded_at")
    date_hierarchy = "uploaded_at"
