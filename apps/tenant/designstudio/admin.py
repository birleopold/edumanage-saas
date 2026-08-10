from django.contrib import admin

from .models import DocumentTemplate, DocumentTemplateVersion, IssuedDocument


class DocumentTemplateVersionInline(admin.TabularInline):
    model = DocumentTemplateVersion
    extra = 0
    readonly_fields = ("number", "status", "created_by", "created_at", "approved_at", "activated_at")


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "document_type", "campus", "level", "active_version_number", "is_default", "is_active")
    list_filter = ("document_type", "is_default", "is_active", "campus")
    search_fields = ("name", "description")
    inlines = [DocumentTemplateVersionInline]


@admin.register(IssuedDocument)
class IssuedDocumentAdmin(admin.ModelAdmin):
    list_display = ("reference", "template", "student", "status", "issued_at")
    list_filter = ("status", "template__document_type")
    search_fields = ("reference", "student__first_name", "student__last_name", "student__student_id")
    readonly_fields = ("verification_token", "data_snapshot", "issued_at")
