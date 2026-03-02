import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    email = models.EmailField(blank=True)

    must_change_password = models.BooleanField(default=False)

    roles = models.ManyToManyField(
        "Role",
        through="UserRole",
        related_name="users",
        blank=True,
    )

    def has_role(self, role_code: str) -> bool:
        return self.roles.filter(code=role_code).exists()

    def __str__(self) -> str:
        return self.get_username()


class Role(models.Model):
    ADMIN = "ADMIN"
    CAMPUS_ADMIN = "CAMPUS_ADMIN"
    TEACHER = "TEACHER"
    STUDENT = "STUDENT"
    PARENT = "PARENT"

    CODE_CHOICES = (
        (ADMIN, "Admin"),
        (CAMPUS_ADMIN, "Campus Admin"),
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
        help_text="Campus scope for campus admin role"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "role", "campus")

    def __str__(self) -> str:
        if self.campus:
            return f"{self.user} -> {self.role} ({self.campus})"
        return f"{self.user} -> {self.role}"


class PasswordSetupToken(models.Model):
    """One-time token for secure password setup via email link."""
    
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
        related_name="created_setup_tokens"
    )
    
    class Meta:
        ordering = ["-created_at"]
    
    def __str__(self) -> str:
        return f"Setup token for {self.user.username}"
    
    @classmethod
    def create_for_user(cls, user: User, created_by=None, validity_hours: int = 72):
        """Create a new setup token valid for specified hours (default 72h)."""
        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(hours=validity_hours)
        return cls.objects.create(
            user=user,
            token=token,
            expires_at=expires_at,
            created_by=created_by
        )
    
    def is_valid(self) -> bool:
        """Check if token is still valid (not used and not expired)."""
        if self.used_at is not None:
            return False
        return timezone.now() < self.expires_at
    
    def mark_used(self):
        """Mark token as used."""
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])
