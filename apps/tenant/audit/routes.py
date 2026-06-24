from django.urls import path

from . import privacy, screens, twofactor

urlpatterns = [
    path("", screens.dashboard, name="audit_dashboard"),
    path("activity/", screens.activity_timeline, name="audit_activity_timeline"),
    path("permissions/", screens.permission_review, name="audit_permission_review"),
    path("retention/", screens.retention_rules, name="audit_retention_rules"),
    path("backups/", screens.backup_jobs, name="audit_backup_jobs"),
    path("verify/", twofactor.verify_2fa, name="audit_verify_2fa"),
    path("accept/", privacy.accept_privacy, name="audit_privacy_accept"),
]