from .services import scoped_recipients
from apps.tenant.finance.communication_providers import send_email_notice


def send_announcement_email(announcement):
    recipients = scoped_recipients(audience_role=announcement.audience, campus=announcement.campus, class_group=announcement.class_group)
    sent = failed = 0
    for user in recipients:
        result = send_email_notice(user.email, announcement.title, announcement.content)
        if result.get("ok"):
            sent += 1
        else:
            failed += 1
    return {"recipients": recipients.count(), "sent": sent, "failed": failed}
