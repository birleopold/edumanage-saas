import hashlib
import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class AttendanceSession(models.Model):
    offering = models.ForeignKey("academics.CourseOffering", on_delete=models.CASCADE)
    date = models.DateField()
    taken_by = models.ForeignKey(
        "teachers.TeacherProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("offering", "date")
        ordering = ("-date", "-created_at")

    def __str__(self) -> str:
        return f"{self.offering} @ {self.date}"


class AttendanceEntry(models.Model):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    LATE = "LATE"
    EXCUSED = "EXCUSED"

    STATUS_CHOICES = (
        (PRESENT, "Present"),
        (ABSENT, "Absent"),
        (LATE, "Late"),
        (EXCUSED, "Excused"),
    )

    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name="entries")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PRESENT)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ("session", "student")
        ordering = ("student__last_name", "student__first_name")

    def __str__(self) -> str:
        return f"{self.student} -> {self.session} ({self.status})"


class AttendanceDevice(models.Model):
    GENERIC = "GENERIC"
    ZKTECO = "ZKTECO"
    HIKVISION = "HIKVISION"
    SUPREMA = "SUPREMA"
    OTHER = "OTHER"
    VENDOR_CHOICES = (
        (GENERIC, "Generic / canonical API"),
        (ZKTECO, "ZKTeco"),
        (HIKVISION, "Hikvision"),
        (SUPREMA, "Suprema"),
        (OTHER, "Other vendor"),
    )

    PUSH = "PUSH"
    PULL = "PULL"
    EDGE = "EDGE"
    FILE = "FILE"
    CONNECTION_CHOICES = (
        (PUSH, "Direct push / webhook"),
        (PULL, "Server or vendor API pull"),
        (EDGE, "Local edge connector"),
        (FILE, "File / CSV import"),
    )

    name = models.CharField(max_length=160)
    code = models.CharField(max_length=120, unique=True)
    serial_number = models.CharField(max_length=160, blank=True, db_index=True)
    vendor = models.CharField(max_length=24, choices=VENDOR_CHOICES, default=GENERIC)
    model_name = models.CharField(max_length=120, blank=True)
    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_devices",
    )
    location = models.CharField(max_length=160, blank=True)
    connection_mode = models.CharField(max_length=16, choices=CONNECTION_CHOICES, default=PUSH)
    protocol = models.CharField(max_length=80, blank=True)
    identity_namespace = models.CharField(
        max_length=80,
        default="default",
        help_text="Devices sharing the same user-number namespace can reuse one identity mapping registry.",
    )
    timezone_name = models.CharField(max_length=64, default="Africa/Kampala")
    capabilities = models.JSONField(default=dict, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    token_prefix = models.CharField(max_length=16, blank=True, db_index=True)
    token_hash = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    last_event_at = models.DateTimeField(null=True, blank=True)
    clock_offset_seconds = models.IntegerField(default=0)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("campus__name", "name")

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"

    @staticmethod
    def hash_token(raw_token: str) -> str:
        return hashlib.sha256((raw_token or "").encode("utf-8")).hexdigest()

    def rotate_token(self) -> str:
        raw_token = secrets.token_urlsafe(36)
        self.token_prefix = raw_token[:10]
        self.token_hash = self.hash_token(raw_token)
        self.save(update_fields=["token_prefix", "token_hash", "updated_at"])
        return raw_token

    def verify_token(self, raw_token: str) -> bool:
        if not raw_token or not self.token_hash:
            return False
        return secrets.compare_digest(self.token_hash, self.hash_token(raw_token))

    @property
    def online(self) -> bool:
        if not self.last_seen_at:
            return False
        threshold = int((self.settings or {}).get("online_window_seconds", 600))
        return self.last_seen_at >= timezone.now() - timezone.timedelta(seconds=max(60, threshold))


class AttendanceIdentity(models.Model):
    STUDENT = "STUDENT"
    STAFF = "STAFF"
    PERSON_CHOICES = ((STUDENT, "Student"), (STAFF, "Staff"))

    namespace = models.CharField(max_length=80, default="default")
    external_person_id = models.CharField(max_length=160)
    person_type = models.CharField(max_length=16, choices=PERSON_CHOICES)
    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="attendance_device_identities",
    )
    staff = models.ForeignKey(
        "hr.StaffProfile",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="attendance_device_identities",
    )
    card_number = models.CharField(max_length=160, blank=True, db_index=True)
    source = models.CharField(max_length=32, default="MANUAL")
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("namespace", "external_person_id")
        constraints = [
            models.UniqueConstraint(
                fields=["namespace", "external_person_id"],
                name="uniq_att_identity_namespace_person",
            )
        ]

    def clean(self):
        super().clean()
        if self.person_type == self.STUDENT:
            if not self.student_id or self.staff_id:
                raise ValidationError("A student identity must link to exactly one student.")
        elif self.person_type == self.STAFF:
            if not self.staff_id or self.student_id:
                raise ValidationError("A staff identity must link to exactly one staff member.")

    def __str__(self) -> str:
        target = self.student if self.student_id else self.staff
        return f"{self.namespace}:{self.external_person_id} -> {target}"


class AttendancePolicy(models.Model):
    STUDENT = AttendanceIdentity.STUDENT
    STAFF = AttendanceIdentity.STAFF
    PERSON_CHOICES = AttendanceIdentity.PERSON_CHOICES

    DEVICE = "DEVICE"
    FIRST_LAST = "FIRST_LAST"
    ALTERNATE = "ALTERNATE"
    DIRECTION_CHOICES = (
        (DEVICE, "Trust device IN/OUT direction"),
        (FIRST_LAST, "First scan in / last scan out"),
        (ALTERNATE, "Alternate IN and OUT scans"),
    )

    name = models.CharField(max_length=160)
    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="attendance_policies",
    )
    person_type = models.CharField(max_length=16, choices=PERSON_CHOICES)
    expected_in = models.TimeField(null=True, blank=True)
    expected_out = models.TimeField(null=True, blank=True)
    late_grace_minutes = models.PositiveSmallIntegerField(default=10)
    early_departure_grace_minutes = models.PositiveSmallIntegerField(default=10)
    duplicate_window_seconds = models.PositiveIntegerField(default=90)
    minimum_presence_minutes = models.PositiveIntegerField(default=0)
    direction_strategy = models.CharField(max_length=16, choices=DIRECTION_CHOICES, default=FIRST_LAST)
    weekdays = models.JSONField(default=list, blank=True, help_text="ISO weekday numbers: Monday=0 through Sunday=6. Blank means Monday-Friday.")
    notify_parent_on_arrival = models.BooleanField(default=False)
    notify_parent_on_departure = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("person_type", "campus__name", "name")

    def __str__(self) -> str:
        scope = self.campus.name if self.campus_id else "All campuses"
        return f"{self.name} - {self.person_type} - {scope}"

    def applies_on(self, day) -> bool:
        weekdays = self.weekdays or [0, 1, 2, 3, 4]
        return day.weekday() in weekdays


class AttendanceEvent(models.Model):
    PUSH = "PUSH"
    PULL = "PULL"
    EDGE = "EDGE"
    FILE = "FILE"
    LEGACY = "LEGACY"
    MANUAL = "MANUAL"
    SOURCE_CHOICES = (
        (PUSH, "Direct push"),
        (PULL, "Pulled from vendor"),
        (EDGE, "Edge connector"),
        (FILE, "File import"),
        (LEGACY, "Legacy integration API"),
        (MANUAL, "Manual entry"),
    )

    IN = "IN"
    OUT = "OUT"
    BREAK_OUT = "BREAK_OUT"
    BREAK_IN = "BREAK_IN"
    UNKNOWN = "UNKNOWN"
    DIRECTION_CHOICES = (
        (IN, "In"),
        (OUT, "Out"),
        (BREAK_OUT, "Break out"),
        (BREAK_IN, "Break in"),
        (UNKNOWN, "Unknown"),
    )

    FACE = "FACE"
    FINGERPRINT = "FINGERPRINT"
    RFID = "RFID"
    PIN = "PIN"
    QR = "QR"
    PALM = "PALM"
    MOBILE = "MOBILE"
    AUTH_UNKNOWN = "UNKNOWN"
    AUTH_CHOICES = (
        (FACE, "Face"),
        (FINGERPRINT, "Fingerprint"),
        (RFID, "RFID / card"),
        (PIN, "PIN"),
        (QR, "QR code"),
        (PALM, "Palm"),
        (MOBILE, "Mobile"),
        (AUTH_UNKNOWN, "Unknown"),
    )

    RECEIVED = "RECEIVED"
    PROCESSED = "PROCESSED"
    DUPLICATE = "DUPLICATE"
    UNMATCHED = "UNMATCHED"
    IGNORED = "IGNORED"
    ERROR = "ERROR"
    PROCESS_CHOICES = (
        (RECEIVED, "Received"),
        (PROCESSED, "Processed"),
        (DUPLICATE, "Duplicate"),
        (UNMATCHED, "Unmatched identity"),
        (IGNORED, "Ignored"),
        (ERROR, "Error"),
    )

    device = models.ForeignKey(AttendanceDevice, on_delete=models.CASCADE, related_name="events")
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default=PUSH)
    external_event_id = models.CharField(max_length=180, blank=True, db_index=True)
    external_person_id = models.CharField(max_length=160, blank=True, db_index=True)
    identity = models.ForeignKey(AttendanceIdentity, on_delete=models.SET_NULL, null=True, blank=True, related_name="events")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="device_attendance_events")
    staff = models.ForeignKey("hr.StaffProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="device_attendance_events")
    occurred_at = models.DateTimeField(db_index=True)
    received_at = models.DateTimeField(default=timezone.now, db_index=True)
    direction = models.CharField(max_length=16, choices=DIRECTION_CHOICES, default=UNKNOWN)
    raw_direction = models.CharField(max_length=80, blank=True)
    auth_method = models.CharField(max_length=16, choices=AUTH_CHOICES, default=AUTH_UNKNOWN)
    event_code = models.CharField(max_length=120, blank=True)
    event_hash = models.CharField(max_length=64, unique=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    processing_status = models.CharField(max_length=16, choices=PROCESS_CHOICES, default=RECEIVED, db_index=True)
    error_message = models.TextField(blank=True)
    clock_skew_seconds = models.IntegerField(default=0)
    server_time_used = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    arrival_notified = models.BooleanField(default=False)
    departure_notified = models.BooleanField(default=False)

    class Meta:
        ordering = ("-occurred_at", "-id")

    def __str__(self) -> str:
        return f"{self.device.code} {self.external_person_id} @ {self.occurred_at}"


class AttendanceDailyRecord(models.Model):
    PRESENT = "PRESENT"
    LATE = "LATE"
    PARTIAL = "PARTIAL"
    ABSENT = "ABSENT"
    EXCUSED = "EXCUSED"
    STATUS_CHOICES = (
        (PRESENT, "Present"),
        (LATE, "Late"),
        (PARTIAL, "Partial day"),
        (ABSENT, "Absent"),
        (EXCUSED, "Excused"),
    )

    date = models.DateField(db_index=True)
    person_type = models.CharField(max_length=16, choices=AttendanceIdentity.PERSON_CHOICES)
    campus = models.ForeignKey("orgsettings.Campus", on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_daily_records")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, null=True, blank=True, related_name="daily_presence_records")
    staff = models.ForeignKey("hr.StaffProfile", on_delete=models.CASCADE, null=True, blank=True, related_name="daily_presence_records")
    policy = models.ForeignKey(AttendancePolicy, on_delete=models.SET_NULL, null=True, blank=True, related_name="daily_records")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PRESENT, db_index=True)
    first_in = models.DateTimeField(null=True, blank=True)
    last_out = models.DateTimeField(null=True, blank=True)
    minutes_late = models.PositiveIntegerField(default=0)
    minutes_early_departure = models.PositiveIntegerField(default=0)
    minutes_present = models.PositiveIntegerField(default=0)
    source_event_count = models.PositiveIntegerField(default=0)
    open_presence = models.BooleanField(default=False)
    manual_override = models.BooleanField(default=False)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-date", "person_type", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["date", "student"],
                condition=Q(student__isnull=False),
                name="uniq_att_daily_student",
            ),
            models.UniqueConstraint(
                fields=["date", "staff"],
                condition=Q(staff__isnull=False),
                name="uniq_att_daily_staff",
            ),
        ]

    def clean(self):
        super().clean()
        if self.person_type == AttendanceIdentity.STUDENT:
            if not self.student_id or self.staff_id:
                raise ValidationError("Student daily attendance must link to one student only.")
        elif self.person_type == AttendanceIdentity.STAFF:
            if not self.staff_id or self.student_id:
                raise ValidationError("Staff daily attendance must link to one staff member only.")

    def __str__(self) -> str:
        target = self.student if self.student_id else self.staff
        return f"{target} - {self.date} - {self.status}"


class AttendanceAdjustment(models.Model):
    record = models.ForeignKey(AttendanceDailyRecord, on_delete=models.CASCADE, related_name="adjustments")
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    reason = models.TextField()
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Attendance adjustment #{self.id} for record {self.record_id}"


class AttendanceSyncCursor(models.Model):
    device = models.ForeignKey(AttendanceDevice, on_delete=models.CASCADE, related_name="sync_cursors")
    cursor_key = models.CharField(max_length=80, default="events")
    cursor_value = models.CharField(max_length=255, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("device", "cursor_key")
        constraints = [
            models.UniqueConstraint(fields=["device", "cursor_key"], name="uniq_att_sync_cursor")
        ]

    def __str__(self) -> str:
        return f"{self.device.code}:{self.cursor_key}={self.cursor_value}"
