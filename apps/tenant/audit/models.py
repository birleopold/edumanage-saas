from django.db import models
from django.utils import timezone


class AuditEvent(models.Model):
    VIEW = "VIEW"
    CREATE = "CREATE"
    EDIT = "EDIT"
    DELETE = "DELETE"
    EXPORT = "EXPORT"
    PRINT = "PRINT"
    DOWNLOAD = "DOWNLOAD"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    PASSWORD = "PASSWORD"
    ACTION_CHOICES = ((VIEW, "View"), (CREATE, "Create"), (EDIT, "Edit"), (DELETE, "Delete"), (EXPORT, "Export"), (PRINT, "Print"), (DOWNLOAD, "Download"), (LOGIN, "Login"), (LOGOUT, "Logout"), (PASSWORD, "Password"))

    user = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_events")
    action = models.CharField(max_length=24, choices=ACTION_CHOICES, db_index=True)
    path = models.CharField(max_length=500, blank=True)
    method = models.CharField(max_length=12, blank=True)
    view_name = models.CharField(max_length=180, blank=True)
    object_label = models.CharField(max_length=255, blank=True)
    campus = models.ForeignKey("orgsettings.Campus", on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    query_params = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["user", "action", "created_at"]), models.Index(fields=["action", "created_at"]), models.Index(fields=["path"])]

    def __str__(self):
        return f"{self.action} {self.user or '-'} {self.path}"


class LoginHistory(models.Model):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    LOGOUT = "LOGOUT"
    STATUS_CHOICES = ((SUCCESS, "Success"), (FAILED, "Failed"), (LOGOUT, "Logout"))

    user = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="login_history")
    username = models.CharField(max_length=180, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["username", "status", "created_at"]), models.Index(fields=["ip_address", "created_at"])]

    def __str__(self):
        return f"{self.username} {self.status}"


class UserTwoFactorSetting(models.Model):
    user = models.OneToOneField("users.User", on_delete=models.CASCADE, related_name="two_factor_setting")
    is_enabled = models.BooleanField(default=False)
    method = models.CharField(max_length=24, default="EMAIL")
    secret = models.CharField(max_length=255, blank=True)
    backup_codes_hash = models.JSONField(default=list, blank=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("user__username",)

    def __str__(self):
        return f"2FA {self.user} {'on' if self.is_enabled else 'off'}"


class ExportPermission(models.Model):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="export_permissions")
    module = models.CharField(max_length=80)
    can_export = models.BooleanField(default=False)
    can_print = models.BooleanField(default=False)
    can_download = models.BooleanField(default=False)
    granted_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="granted_export_permissions")
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "module")
        ordering = ("module", "user")

    def __str__(self):
        return f"{self.user} - {self.module}"


class DataRetentionPolicy(models.Model):
    module = models.CharField(max_length=80, unique=True)
    retention_days = models.PositiveIntegerField(default=2555)
    action_after_retention = models.CharField(max_length=32, default="ARCHIVE")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("module",)

    def __str__(self):
        return f"{self.module}: {self.retention_days} days"


class ConsentRecord(models.Model):
    PRIVACY = "PRIVACY"
    DATA_PROCESSING = "DATA_PROCESSING"
    PHOTO = "PHOTO"
    MEDICAL = "MEDICAL"
    COMMUNICATION = "COMMUNICATION"
    CONSENT_CHOICES = ((PRIVACY, "Privacy policy"), (DATA_PROCESSING, "Data processing"), (PHOTO, "Photo/media"), (MEDICAL, "Medical/emergency"), (COMMUNICATION, "Communication"))

    user = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="consent_records")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="consent_records")
    parent = models.ForeignKey("parents.ParentProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="consent_records")
    consent_type = models.CharField(max_length=32, choices=CONSENT_CHOICES)
    accepted = models.BooleanField(default=True)
    version = models.CharField(max_length=32, default="1.0")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    note = models.TextField(blank=True)
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-recorded_at",)
        indexes = [models.Index(fields=["consent_type", "accepted", "recorded_at"])]

    def __str__(self):
        return f"{self.consent_type} {self.user or self.parent or self.student}"


class BackupJob(models.Model):
    REQUESTED = "REQUESTED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RESTORE_TESTED = "RESTORE_TESTED"
    STATUS_CHOICES = ((REQUESTED, "Requested"), (RUNNING, "Running"), (SUCCESS, "Success"), (FAILED, "Failed"), (RESTORE_TESTED, "Restore tested"))

    requested_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=REQUESTED)
    file_path = models.CharField(max_length=500, blank=True)
    checksum = models.CharField(max_length=128, blank=True)
    notes = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Backup {self.id} {self.status}"


class SuspiciousLoginAlert(models.Model):
    OPEN = "OPEN"
    REVIEWED = "REVIEWED"
    DISMISSED = "DISMISSED"
    STATUS_CHOICES = ((OPEN, "Open"), (REVIEWED, "Reviewed"), (DISMISSED, "Dismissed"))

    user = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="suspicious_login_alerts")
    username = models.CharField(max_length=180, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    reason = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=OPEN)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_login_alerts")
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["status", "created_at"]), models.Index(fields=["username", "ip_address"])]

    def __str__(self):
        return f"Suspicious login {self.username} {self.ip_address}"
