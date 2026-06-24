from django.conf import settings
from django.db import models


class WebPushSubscription(models.Model):
    """Browser push subscription saved per tenant user.

    This makes the PWA push layer production-ready without Node/npm. A separate
    Python/Django delivery job can later read active subscriptions and send push
    messages through a VAPID/web-push provider.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="web_push_subscriptions")
    endpoint = models.TextField(unique=True)
    p256dh_key = models.TextField(blank=True)
    auth_key = models.TextField(blank=True)
    user_agent = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        ordering = ("-updated_at",)
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["is_active", "updated_at"]),
        ]

    def __str__(self):
        return f"{self.user} push subscription"
