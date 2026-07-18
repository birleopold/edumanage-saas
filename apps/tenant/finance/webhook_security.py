import ipaddress
import socket
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError

BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain", "metadata.google.internal", "metadata.google"}

def _is_public_ip(value):
    address = ipaddress.ip_address(value)
    return not (address.is_private or address.is_loopback or address.is_link_local or address.is_multicast or address.is_reserved or address.is_unspecified)

def validate_webhook_target(target_url):
    parsed = urlsplit(target_url or "")
    if parsed.scheme not in {"https", "http"}:
        raise ValidationError("Webhook URL must use HTTPS.")
    if parsed.scheme == "http" and not getattr(settings, "WEBHOOK_ALLOW_HTTP", False):
        raise ValidationError("Production webhook URLs must use HTTPS.")
    if parsed.username or parsed.password:
        raise ValidationError("Webhook URLs may not contain embedded credentials.")
    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if not hostname:
        raise ValidationError("Webhook URL must include a hostname.")
    if hostname in set(getattr(settings, "WEBHOOK_ALLOWED_HOSTS", ()) or ()):
        return target_url
    if hostname in BLOCKED_HOSTNAMES or hostname.endswith(".local") or hostname.endswith(".internal"):
        raise ValidationError("Webhook destination is not allowed.")
    if getattr(settings, "WEBHOOK_ALLOW_PRIVATE_TARGETS", False):
        return target_url
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise ValidationError("Webhook hostname could not be resolved.") from exc
    if not addresses or any(not _is_public_ip(address) for address in addresses):
        raise ValidationError("Webhook destination must resolve only to public IP addresses.")
    return target_url
