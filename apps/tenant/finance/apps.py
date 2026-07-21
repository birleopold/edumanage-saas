from django.apps import AppConfig


class FinanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenant.finance"
    label = "finance"

    def ready(self):
        from . import (  # noqa: F401
            accounting_models,
            clearance_models,
            integration_models,
            payment_gateway_models,
            signals,
        )
        from .webhook_security import install_webhook_delivery_guard

        install_webhook_delivery_guard()
