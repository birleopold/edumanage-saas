# Generated for EduManage platform audit visibility.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tenants", "0002_domain_dns_ssl_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlatformAuditEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("TENANT_CREATED", "Tenant created"),
                            ("TENANT_STATUS_CHANGED", "Tenant status changed"),
                            ("TENANT_SUSPENDED", "Tenant suspended"),
                            ("TENANT_REACTIVATED", "Tenant reactivated"),
                            ("DOMAIN_CREATED", "Domain created"),
                            ("DOMAIN_UPDATED", "Domain updated"),
                            ("DOMAIN_VERIFIED", "Domain verified"),
                            ("DOMAIN_SSL_UPDATED", "Domain SSL updated"),
                        ],
                        db_index=True,
                        max_length=40,
                    ),
                ),
                ("object_label", models.CharField(blank=True, max_length=255)),
                ("before", models.JSONField(blank=True, default=dict)),
                ("after", models.JSONField(blank=True, default=dict)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="platform_audit_events", to=settings.AUTH_USER_MODEL)),
                ("domain", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="platform_audit_events", to="tenants.domain")),
                ("tenant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="platform_audit_events", to="tenants.tenant")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddIndex(
            model_name="platformauditevent",
            index=models.Index(fields=["action", "created_at"], name="tenants_pla_action__6226d0_idx"),
        ),
        migrations.AddIndex(
            model_name="platformauditevent",
            index=models.Index(fields=["tenant", "created_at"], name="tenants_pla_tenant__721b7b_idx"),
        ),
        migrations.AddIndex(
            model_name="platformauditevent",
            index=models.Index(fields=["actor", "created_at"], name="tenants_pla_actor_i_f6637b_idx"),
        ),
    ]
