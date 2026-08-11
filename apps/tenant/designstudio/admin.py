from django.contrib import admin

from .models import DocumentTemplate, DocumentTemplateVersion, IssuedDocument


class DocumentTemplateVersionInline(admin.TabularInline):
    model = DocumentTemplateVersion
    extra = 0
    can_delete = False
    show_change_link = False
    fields = ("number", "status", "page_width_mm", "page_height_mm", "created_by", "created_at", "submitted_at", "approved_at", "activated_at")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        # Versions must be created through Design Studio so lifecycle and
        # immutability rules cannot be bypassed from Django admin.
        return False


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "document_type", "campus", "level", "active_version_number", "is_default", "is_active")
    list_filter = ("document_type", "is_default", "is_active", "campus")
    search_fields = ("name", "description")
    readonly_fields = ("active_version_number", "created_by", "updated_by", "created_at", "updated_at")
    inlines = [DocumentTemplateVersionInline]

    def has_add_permission(self, request):
        # Creation through the portal guarantees an initial validated draft.
        return False

    def has_delete_permission(self, request, obj=None):
        # Historical templates may be referenced by issued documents. Deactivate
        # them from Design Studio instead of deleting records.
        return False


@admin.register(IssuedDocument)
class IssuedDocumentAdmin(admin.ModelAdmin):
    list_display = ("reference", "template", "student", "status", "issued_at")
    list_filter = ("status", "template__document_type")
    search_fields = ("reference", "student__first_name", "student__last_name", "student__student_id")
    readonly_fields = (
        "template",
        "version",
        "student",
        "academic_term",
        "reference",
        "verification_token",
        "status",
        "data_snapshot",
        "pdf_file",
        "issued_by",
        "issued_at",
        "revoked_by",
        "revoked_at",
        "revocation_reason",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        # Verification history must remain available even after revocation.
        return False
