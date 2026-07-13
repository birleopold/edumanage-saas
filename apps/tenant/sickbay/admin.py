from django.contrib import admin

from .models import SickbayVisit, StudentMedicalProfile


@admin.register(StudentMedicalProfile)
class StudentMedicalProfileAdmin(admin.ModelAdmin):
    list_display = ("student", "blood_group", "emergency_contact_phone", "updated_at")
    search_fields = ("student__first_name", "student__last_name", "student__student_id", "allergies", "chronic_conditions")


@admin.register(SickbayVisit)
class SickbayVisitAdmin(admin.ModelAdmin):
    list_display = ("student", "complaint", "severity", "outcome", "parent_notified", "visit_at")
    list_filter = ("severity", "outcome", "parent_notified", "visit_at")
    search_fields = ("student__first_name", "student__last_name", "student__student_id", "complaint", "symptoms")
