from django.db import models
from django.utils import timezone


class IntegrationProviderConfig(models.Model):
    BIOMETRIC = "BIOMETRIC"
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"
    EMAIL = "EMAIL"
    MTN_MOMO = "MTN_MOMO"
    AIRTEL_MONEY = "AIRTEL_MONEY"
    GOOGLE_MEET = "GOOGLE_MEET"
    ZOOM = "ZOOM"
    BIGBLUEBUTTON = "BIGBLUEBUTTON"
    GOOGLE_LOGIN = "GOOGLE_LOGIN"
    MICROSOFT_LOGIN = "MICROSOFT_LOGIN"
    GPS = "GPS"
    OTHER = "OTHER"
    PROVIDER_CHOICES = (
        (BIOMETRIC, "Biometric Attendance"),
        (SMS, "SMS Gateway"),
        (WHATSAPP, "WhatsApp Cloud API"),
        (EMAIL, "Email Gateway"),
        (MTN_MOMO, "MTN MoMo"),
        (AIRTEL_MONEY, "Airtel Money"),
        (GOOGLE_MEET, "Google Meet"),
        (ZOOM, "Zoom"),
        (BIGBLUEBUTTON, "BigBlueButton"),
        (GOOGLE_LOGIN, "Google Login"),
        (MICROSOFT_LOGIN, "Microsoft Login"),
        (GPS, "Vehicle GPS"),
        (OTHER, "Other"),
    )

    name = models.CharField(max_length=120)
    provider_type = models.CharField(max_length=32, choices=PROVIDER_CHOICES)
    base_url = models.URLField(blank=True, max_length=400)
    client_id = models.CharField(max_length=255, blank=True)
    client_secret = models.CharField(max_length=255, blank=True)
    access_token = models.TextField(blank=True)
    webhook_secret = models.CharField(max_length=255, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_status = models.CharField(max_length=32, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "finance"
        ordering = ("provider_type", "name")
        indexes = [models.Index(fields=["provider_type", "is_active"])]

    def __str__(self):
        return f"{self.get_provider_type_display()} - {self.name}"


class IntegrationScope(models.Model):
    code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "finance"
        ordering = ("code",)

    def __str__(self):
        return self.code


class IntegrationApiKeyScope(models.Model):
    api_key = models.ForeignKey("finance.IntegrationApiKey", on_delete=models.CASCADE, related_name="scope_links")
    scope = models.ForeignKey(IntegrationScope, on_delete=models.CASCADE, related_name="api_key_links")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "finance"
        unique_together = ("api_key", "scope")
        ordering = ("api_key", "scope")

    def __str__(self):
        return f"{self.api_key} -> {self.scope}"


class IntegrationEventLog(models.Model):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"
    DIRECTION_CHOICES = ((INBOUND, "Inbound"), (OUTBOUND, "Outbound"))
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PENDING = "PENDING"
    STATUS_CHOICES = ((SUCCESS, "Success"), (FAILED, "Failed"), (PENDING, "Pending"))

    provider = models.ForeignKey(IntegrationProviderConfig, on_delete=models.SET_NULL, null=True, blank=True, related_name="event_logs")
    event_type = models.CharField(max_length=120)
    direction = models.CharField(max_length=16, choices=DIRECTION_CHOICES, default=INBOUND)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PENDING)
    external_reference = models.CharField(max_length=160, blank=True, db_index=True)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    api_key = models.ForeignKey("finance.IntegrationApiKey", on_delete=models.SET_NULL, null=True, blank=True, related_name="integration_events")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "finance"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["event_type", "status", "created_at"]), models.Index(fields=["external_reference"])]

    def __str__(self):
        return f"{self.event_type} - {self.status}"


class BiometricDevice(models.Model):
    name = models.CharField(max_length=120)
    device_code = models.CharField(max_length=120, unique=True)
    campus = models.ForeignKey("orgsettings.Campus", on_delete=models.SET_NULL, null=True, blank=True)
    provider = models.ForeignKey(IntegrationProviderConfig, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "finance"
        ordering = ("name",)

    def __str__(self):
        return self.name


class BiometricAttendanceEvent(models.Model):
    device = models.ForeignKey(BiometricDevice, on_delete=models.SET_NULL, null=True, blank=True, related_name="events")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="biometric_events")
    external_person_id = models.CharField(max_length=120, blank=True)
    event_time = models.DateTimeField(default=timezone.now)
    offering = models.ForeignKey("academics.CourseOffering", on_delete=models.SET_NULL, null=True, blank=True)
    attendance_entry = models.ForeignKey("attendance.AttendanceEntry", on_delete=models.SET_NULL, null=True, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    processed = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)

    class Meta:
        app_label = "finance"
        ordering = ("-event_time",)
        indexes = [models.Index(fields=["external_person_id", "event_time"]), models.Index(fields=["processed"])]

    def __str__(self):
        return f"Biometric event {self.external_person_id} @ {self.event_time}"


class MeetingSessionLink(models.Model):
    GOOGLE_MEET = "GOOGLE_MEET"
    ZOOM = "ZOOM"
    BIGBLUEBUTTON = "BIGBLUEBUTTON"
    PROVIDER_CHOICES = ((GOOGLE_MEET, "Google Meet"), (ZOOM, "Zoom"), (BIGBLUEBUTTON, "BigBlueButton"))

    provider_type = models.CharField(max_length=32, choices=PROVIDER_CHOICES)
    provider = models.ForeignKey(IntegrationProviderConfig, on_delete=models.SET_NULL, null=True, blank=True)
    offering = models.ForeignKey("academics.CourseOffering", on_delete=models.SET_NULL, null=True, blank=True, related_name="meeting_links")
    title = models.CharField(max_length=180)
    meeting_url = models.URLField(max_length=500)
    external_meeting_id = models.CharField(max_length=160, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "finance"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.title} - {self.provider_type}"


class SSOLoginProvider(models.Model):
    GOOGLE = "GOOGLE"
    MICROSOFT = "MICROSOFT"
    PROVIDER_CHOICES = ((GOOGLE, "Google"), (MICROSOFT, "Microsoft"))

    provider_type = models.CharField(max_length=32, choices=PROVIDER_CHOICES)
    name = models.CharField(max_length=120)
    client_id = models.CharField(max_length=255)
    client_secret = models.CharField(max_length=255, blank=True)
    authorization_url = models.URLField(max_length=400)
    token_url = models.URLField(max_length=400, blank=True)
    userinfo_url = models.URLField(max_length=400, blank=True)
    scopes = models.CharField(max_length=255, default="openid email profile")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "finance"
        ordering = ("provider_type", "name")

    def __str__(self):
        return self.name
