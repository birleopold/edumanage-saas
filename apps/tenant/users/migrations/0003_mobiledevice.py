# Generated manually for mobile app push-device registration

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_role_userrole_user_roles"),
    ]

    operations = [
        migrations.CreateModel(
            name="MobileDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("platform", models.CharField(choices=[("IOS", "iOS"), ("ANDROID", "Android"), ("WEB", "Web/PWA")], max_length=16)),
                ("device_id", models.CharField(blank=True, max_length=255)),
                ("push_token", models.CharField(blank=True, max_length=512)),
                ("app_version", models.CharField(blank=True, max_length=64)),
                ("is_active", models.BooleanField(default=True)),
                ("last_seen_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="mobile_devices", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-last_seen_at",), "unique_together": {("user", "platform", "device_id")}},
        ),
        migrations.AddIndex(model_name="mobiledevice", index=models.Index(fields=["user", "is_active"], name="users_mobile_user_active_idx")),
        migrations.AddIndex(model_name="mobiledevice", index=models.Index(fields=["push_token"], name="users_mobile_push_idx")),
    ]
