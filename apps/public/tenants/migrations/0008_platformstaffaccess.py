from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    dependencies = [("tenants", "0007_platformtwofactorsetting")]
    operations = [
        migrations.CreateModel(
            name="PlatformStaffAccess",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("OWNER","Owner"),("SUPPORT","Support"),("ONBOARDING","Onboarding"),("BILLING","Billing")], max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="platform_staff_access", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
