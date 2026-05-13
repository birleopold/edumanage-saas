"""
Optional SMS handlers for FEE_REMINDER_HANDLER (or legacy FEE_REMINDER_SMS_HANDLER).

Example in settings:
    FEE_REMINDER_HANDLER = "apps.tenant.finance.sms_defaults.log_fee_reminder_to_logger"
"""
import logging

logger = logging.getLogger("edumanage.finance.sms")


def log_fee_reminder_to_logger(phone: str, message: str, channel: str = "SMS") -> bool:
    """Development-friendly handler: logs the payload, returns True."""
    logger.info(
        "Fee reminder channel=%s phone=%s message=%s",
        channel,
        phone,
        (message or "")[:400],
    )
    return True
