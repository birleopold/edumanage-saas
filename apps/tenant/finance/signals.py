import logging

from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import InvoiceLine, Payment, WebhookEndpoint
from .webhook_security import validate_webhook_target


logger = logging.getLogger("edumanage.finance")


@receiver(pre_save, sender=WebhookEndpoint)
def validate_webhook_endpoint_target(sender, instance, **kwargs):
    validate_webhook_target(instance.target_url)


@receiver(post_save, sender=Payment)
def enforce_payment_ledger_posting(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from .accounting_posting import post_payment_to_ledger

        post_payment_to_ledger(instance)
        instance._ledger_posted_by_signal = True
    except Exception as exc:
        logger.exception("Rolling back payment because ledger posting failed payment_id=%s", instance.pk)
        sender.objects.filter(pk=instance.pk).delete()
        raise ValidationError("Payment was not saved because its accounting entry could not be posted.") from exc


@receiver(post_save, sender=InvoiceLine)
def enforce_invoice_ledger_refresh(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from .accounting_posting import refresh_invoice_ledger

        refresh_invoice_ledger(instance.invoice)
        instance.invoice._ledger_refreshed_by_signal = True
    except Exception as exc:
        logger.exception("Rolling back invoice line because ledger refresh failed invoice_line_id=%s", instance.pk)
        invoice = instance.invoice
        sender.objects.filter(pk=instance.pk).delete()
        try:
            from .accounting_posting import refresh_invoice_ledger

            refresh_invoice_ledger(invoice)
        except Exception:
            logger.exception("Could not restore invoice ledger after invoice-line rollback invoice_id=%s", invoice.pk)
        raise ValidationError("Invoice line was not saved because its accounting entry could not be refreshed.") from exc
