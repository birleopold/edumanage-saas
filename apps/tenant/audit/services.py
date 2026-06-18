from django.utils import timezone

from .models import AuditEvent, ExportPermission, LoginHistory, SuspiciousLoginAlert


SENSITIVE_KEYS = {"password", "token", "secret", "client_secret", "access_token", "key_hash", "api_key"}


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def user_agent(request):
    return request.META.get("HTTP_USER_AGENT", "")[:1000]


def safe_params(querydict):
    data = {}
    for key, value in querydict.items():
        data[key] = "***" if key.lower() in SENSITIVE_KEYS else value
    return data


def infer_action(request):
    path = request.path.lower()
    method = request.method.upper()
    if "export" in path or request.GET.get("format") in ["csv", "xlsx", "pdf"]:
        return AuditEvent.EXPORT
    if "print" in path:
        return AuditEvent.PRINT
    if "download" in path or "receipt" in path or "pdf" in path:
        return AuditEvent.DOWNLOAD
    if method == "POST":
        if any(word in path for word in ["delete", "remove", "archive"]):
            return AuditEvent.DELETE
        if any(word in path for word in ["edit", "update", "change"]):
            return AuditEvent.EDIT
        return AuditEvent.CREATE
    return AuditEvent.VIEW


def log_audit(request, action=None, object_label="", metadata=None):
    user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
    if not user:
        return None
    action = action or infer_action(request)
    campus = getattr(request, "current_campus", None)
    try:
        return AuditEvent.objects.create(user=user, action=action, path=request.path[:500], method=request.method, view_name=getattr(getattr(request, "resolver_match", None), "view_name", "") or "", object_label=object_label[:255], campus=campus, ip_address=client_ip(request), user_agent=user_agent(request), query_params=safe_params(request.GET), metadata=metadata or {})
    except Exception:
        return None


def log_login(request, username="", user=None, status=LoginHistory.SUCCESS, reason=""):
    obj = LoginHistory.objects.create(user=user, username=username or getattr(user, "username", ""), status=status, ip_address=client_ip(request), user_agent=user_agent(request), reason=reason)
    if status == LoginHistory.SUCCESS and user:
        previous = LoginHistory.objects.filter(user=user, status=LoginHistory.SUCCESS).exclude(pk=obj.pk).order_by("-created_at").first()
        if previous and previous.ip_address and previous.ip_address != obj.ip_address:
            SuspiciousLoginAlert.objects.create(user=user, username=user.username, ip_address=obj.ip_address, reason="Login from a new IP address", metadata={"previous_ip": previous.ip_address})
    if status == LoginHistory.FAILED:
        cutoff = timezone.now() - timezone.timedelta(minutes=30)
        failures = LoginHistory.objects.filter(username=username, status=LoginHistory.FAILED, created_at__gte=cutoff).count()
        if failures >= 5:
            SuspiciousLoginAlert.objects.create(username=username, ip_address=client_ip(request), reason="Multiple failed login attempts", metadata={"failures_30_minutes": failures})
    return obj


def can_user_export(user, module, action="export"):
    if getattr(user, "is_superuser", False):
        return True
    perm = ExportPermission.objects.filter(user=user, module=module).first()
    if not perm:
        return False
    if action == "print":
        return perm.can_print
    if action == "download":
        return perm.can_download
    return perm.can_export


def mask_sensitive(value):
    if value in [None, ""]:
        return value
    text = str(value)
    if len(text) <= 4:
        return "***"
    return f"***{text[-4:]}"
