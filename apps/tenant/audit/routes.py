from django.urls import path

from . import export_tools, privacy, screens, twofactor

urlpatterns = [
    path("", screens.dashboard, name="audit_dashboard"),
    path("activity/", screens.activity_timeline, name="audit_activity_timeline"),
    path("exports/", export_tools.export_center, name="audit_export_center"),
    path("exports/<slug:export_key>/", export_tools.download_export, name="audit_download_export"),
    path("backup-school-data/", export_tools.request_backup, name="audit_request_backup"),
    path("permissions/", screens.permission_review, name="audit_permission_review"),
    path("retention/", screens.retention_rules, name="audit_retention_rules"),
    path("backups/", screens.backup_jobs, name="audit_backup_jobs"),
    path("two-factor/", twofactor.two_factor_settings, name="audit_two_factor_settings"),
    path("verify/", twofactor.verify_2fa, name="audit_verify_2fa"),
    path("accept/", privacy.accept_privacy, name="audit_privacy_accept"),
]
