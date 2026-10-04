from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("finance", "0017_integration_key_expiry_ip_allowlist")]

    operations = [
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(fields=["invoice", "reference"], name="finance_pay_invoice_72f6d7_idx"),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.UniqueConstraint(
                condition=models.Q(("method", "MOBILE"), models.Q(("reference", ""), _negated=True)),
                fields=("invoice", "method", "mobile_network", "reference"),
                name="finance_unique_mobile_payment_reference",
            ),
        ),
        migrations.AddConstraint(
            model_name="mobilepaymentrequest",
            constraint=models.UniqueConstraint(
                condition=models.Q(("provider_reference", ""), _negated=True),
                fields=("network", "provider_reference"),
                name="finance_unique_provider_request_reference",
            ),
        ),
    ]
