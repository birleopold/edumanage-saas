from apps.tenant.finance.communication_providers import send_email_notice
from apps.tenant.users.models import Role

from .services import scoped_recipients


AUDIENCE_ROLE_MAP = {
    "PARENTS": Role.PARENT,
    "STUDENTS": Role.STUDENT,
    "TEACHERS": Role.TEACHER,
    "STAFF": "ALL",
    "ALL": "ALL",
}


def send_announcement_email(announcement):
    role = AUDIENCE_ROLE_MAP.get(announcement.audience, "ALL")
    recipients = scoped_recipients(audience_role=role, campus=announcement.campus, class_group=announcement.class_group)
    sent = failed = 0
    for user in recipients:
        result = send_email_notice(user.email, announcement.title, announcement.content)
        if result.get("ok"):
            sent += 1
        else:
            failed += 1
    return {"recipients": recipients.count(), "sent": sent, "failed": failed}
