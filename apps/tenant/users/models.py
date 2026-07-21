import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    must_change_password = models.BooleanField(default=False)
    roles = models.ManyToManyField("Role", through="UserRole", related_name="users", blank=True)

    def has_role(self, role_code: str) -> bool:
        return self.roles.filter(code=role_code).exists()

    def get_full_name(self):
        """Return the account name, falling back to its linked school profile."""
        account_name = super().get_full_name().strip()
        if account_name:
            return account_name

        for relation_name in ("student_profile", "teacher_profile", "parent_profile"):
            try:
                profile = getattr(self, relation_name)
            except ObjectDoesNotExist:
                continue

            profile_name = ""
            if hasattr(profile, "get_full_name"):
                profile_name = profile.get_full_name()
            else:
                profile_name = f"{getattr(profile, 'first_name', '')} {getattr(profile, 'last_name', '')}".strip()
            if profile_name:
                return profile_name

        return self.get_username()

    def save(self, *args, **kwargs):
        normalized_email = (self.email or "").strip().lower()
        previous_email = ""
        if self.pk:
            previous_email = type(self).objects.filter(pk=self.pk).values_list("email", flat=True).first() or ""
        email_changed = self._state.adding or normalized_email != previous_email.strip().lower()
        self.email = normalized_email
        if self.email and email_changed:
            duplicate = type(self).objects.filter(email__iexact=self.email).exclude(pk=self.pk).exists()
            if duplicate:
                raise ValidationError({"email": "This email address is already linked to another user."})
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.get_username()


class Role(models.Model):
    ADMIN = "ADMIN"
    CAMPUS_ADMIN = "CAMPUS_ADMIN"
    PRINCIPAL = "PRINCIPAL"
    TEACHER = "TEACHER"
    STUDENT = "STUDENT"
    PARENT = "PARENT"

    CODE_CHOICES = (
        (ADMIN, "Admin"),
        (CAMPUS_ADMIN, "Campus Admin"),
        (PRINCIPAL, "Principal"),
        (TEACHER, "Teacher"),
        (STUDENT, "Student"),
        (PARENT, "Parent"),
    )

    code = models.CharField(max_length=32, unique=True, choices=CODE_CHOICES)
    name = models.CharField(max_length=128)

    def __str__(self) -> str:
        return self.name


class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    campus = models.ForeignKey(
        "orgsettings.Campus",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Campus scope for campus admin role",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "role", "campus")

    def save(self, *args, **kwargs):
        scope_changed = self._state.adding
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values("user_id", "role_id", "campus_id").first()
            scope_changed = not previous or (previous["user_id"], previous["role_id"], previous["campus_id"]) != (self.user_id, self.role_id, self.campus_id)
        if scope_changed:
            existing = type(self).objects.filter(user=self.user, role=self.role)
            existing = existing.filter(campus__isnull=True) if self.campus_id is None else existing.filter(campus_id=self.campus_id)
            if existing.exclude(pk=self.pk).exists():
                raise ValidationError("This role assignment already exists for the selected campus scope.")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        if self.campus:
            return f"{self.user} -> {self.role} ({self.campus})"
        return f"{self.user} -> {self.role}"


class PasswordSetupToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="setup_tokens")
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_setup_tokens",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Setup token for {self.user.username}"

    @classmethod
    def create_for_user(cls, user: User, created_by=None, validity_hours: int = 72):
        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(hours=validity_hours)
        return cls.objects.create(user=user, token=token, expires_at=expires_at, created_by=created_by)

    def is_valid(self) -> bool:
        if self.used_at is not None:
            return False
        return timezone.now() < self.expires_at

    def mark_used(self):
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])


class MobileDevice(models.Model):
    IOS = "IOS"
    ANDROID = "ANDROID"
    WEB = "WEB"
    PLATFORM_CHOICES = ((IOS, "iOS"), (ANDROID, "Android"), (WEB, "Web/PWA"))

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mobile_devices")
    platform = models.CharField(max_length=16, choices=PLATFORM_CHOICES)
    device_id = models.CharField(max_length=255, blank=True)
    push_token = models.CharField(max_length=512, blank=True)
    app_version = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-last_seen_at",)
        unique_together = ("user", "platform", "device_id")
        indexes = [models.Index(fields=["user", "is_active"]), models.Index(fields=["push_token"])]

    def __str__(self) -> str:
        return f"{self.user} {self.platform} {self.device_id or self.id}"
