from django.apps import AppConfig


class FinanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenant.finance"
    label = "finance"

    def ready(self):
        try:
            from . import accounting_models, integration_models, payment_gateway_models  # noqa: F401
        except Exception:
            pass
