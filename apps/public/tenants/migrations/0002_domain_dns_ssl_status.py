# Generated for EduManage platform domain management.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="domain",
            name="dns_status",
            field=models.CharField(
                choices=[("PENDING", "Pending"), ("VERIFIED", "Verified"), ("FAILED", "Failed")],
                default="PENDING",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="domain",
            name="ssl_status",
            field=models.CharField(
                choices=[("PENDING", "Pending"), ("ACTIVE", "Active"), ("FAILED", "Failed"), ("EXPIRED", "Expired")],
                default="PENDING",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="domain",
            name="last_checked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="domain",
            name="dns_notes",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="domain",
            name="type",
            field=models.CharField(
                choices=[("SUBDOMAIN", "Subdomain"), ("CUSTOM", "Custom domain")],
                default="SUBDOMAIN",
                max_length=16,
            ),
        ),
    ]
