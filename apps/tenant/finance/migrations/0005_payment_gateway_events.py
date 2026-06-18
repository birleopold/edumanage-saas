from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("finance", "0004_statement_lines")]

    operations = [
        migrations.CreateModel(
            name="PaymentGatewayEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("MTN_MOMO", "MTN MoMo"), ("AIRTEL_MONEY", "Airtel Money"), ("BANK", "Bank")], max_length=32)),
                ("event_type", models.CharField(choices=[("INITIATED", "Initiated"), ("CALLBACK", "Callback"), ("STATUS_CHECK", "Status check")], default="CALLBACK", max_length=32)),
                ("provider_reference", models.CharField(blank=True, db_index=True, max_length=160)),
                ("provider_status", models.CharField(blank=True, max_length=64)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("processed", models.BooleanField(default=False)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("payment_request", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="gateway_events", to="finance.mobilepaymentrequest")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="DuplicatePaymentAlert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reason", models.CharField(max_length=255)),
                ("is_resolved", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("duplicate_of", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="possible_duplicates", to="finance.payment")),
                ("payment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="duplicate_alerts", to="finance.payment")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddIndex(model_name="paymentgatewayevent", index=models.Index(fields=["provider", "provider_reference"], name="finance_pge_provider_ref_idx")),
        migrations.AddIndex(model_name="paymentgatewayevent", index=models.Index(fields=["processed", "created_at"], name="finance_pge_processed_idx")),
    ]
