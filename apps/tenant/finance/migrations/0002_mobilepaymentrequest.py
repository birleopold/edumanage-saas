# Generated manually for mobile payment initiation tracking

from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MobilePaymentRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("phone_number", models.CharField(max_length=32)),
                ("network", models.CharField(choices=[("MTN_MOMO", "MTN MoMo"), ("AIRTEL_MONEY", "Airtel Money"), ("OTHER", "Other mobile wallet")], default="MTN_MOMO", max_length=16)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("PROCESSING", "Processing"), ("SUCCESSFUL", "Successful"), ("FAILED", "Failed"), ("CANCELLED", "Cancelled")], default="PENDING", max_length=16)),
                ("provider_reference", models.CharField(blank=True, max_length=128)),
                ("provider_response", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_payment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="mobile_requests", to="finance.payment")),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="mobile_payment_requests", to="finance.invoice")),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddIndex(model_name="mobilepaymentrequest", index=models.Index(fields=["invoice", "status"], name="finance_mpr_invoice_status_idx")),
        migrations.AddIndex(model_name="mobilepaymentrequest", index=models.Index(fields=["provider_reference"], name="finance_mpr_provider_ref_idx")),
    ]
