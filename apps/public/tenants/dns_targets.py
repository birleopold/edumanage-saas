from functools import lru_cache
from ipaddress import IPv4Address, ip_address
import socket
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.conf import settings


A_RECORD_PLACEHOLDER = "YOUR_EDUMANAGE_SERVER_IP"
DEFAULT_CNAME_TARGET = "edumanage.com"
PUBLIC_IPV4_ENDPOINTS = (
    "https://api4.ipify.org",
    "https://checkip.amazonaws.com",
)


def _clean_public_ipv4(value):
    value = str(value or "").strip()
    if not value:
        return ""
    try:
        address = ip_address(value)
    except ValueError:
        return ""
    if not isinstance(address, IPv4Address) or not address.is_global:
        return ""
    return str(address)


def _clean_hostname(value):
    value = str(value or "").strip().lower().rstrip(".")
    if not value or "://" in value or "/" in value or " " in value:
        return ""
    if value.startswith("*."):
        value = value[2:]
    elif value.startswith("."):
        value = value[1:]
    if not value or value in {"localhost", "127.0.0.1"}:
        return ""
    return value


def _origin_host_candidates():
    candidates = []
    configured_origin = _clean_hostname(getattr(settings, "EDUMANAGE_ORIGIN_HOST", ""))
    if configured_origin:
        candidates.append(configured_origin)
    for host in getattr(settings, "ALLOWED_HOSTS", []):
        clean_host = _clean_hostname(host)
        if clean_host and clean_host not in candidates:
            candidates.append(clean_host)
    return candidates


def _fetch_public_ipv4():
    for endpoint in PUBLIC_IPV4_ENDPOINTS:
        try:
            request = Request(
                endpoint,
                headers={"User-Agent": "EduManage-DNS-Readiness/1.0"},
            )
            with urlopen(request, timeout=2.0) as response:
                candidate = response.read(64).decode("ascii", errors="ignore").strip()
        except (OSError, TimeoutError, URLError, ValueError):
            continue
        public_ip = _clean_public_ipv4(candidate)
        if public_ip:
            return public_ip
    return ""


def _resolve_origin_ipv4():
    for host in _origin_host_candidates():
        try:
            answers = socket.getaddrinfo(
                host,
                None,
                family=socket.AF_INET,
                type=socket.SOCK_STREAM,
            )
        except OSError:
            continue
        for answer in answers:
            public_ip = _clean_public_ipv4(answer[4][0])
            if public_ip:
                return public_ip
    return ""


@lru_cache(maxsize=1)
def _auto_detect_public_ipv4():
    environment = str(getattr(settings, "ENVIRONMENT", "")).lower()
    if environment == "production":
        detected = _fetch_public_ipv4()
        if detected:
            return detected, "Auto-detected from the VPS public network"
    detected = _resolve_origin_ipv4()
    if detected:
        return detected, "Resolved from the EduManage origin hostname"
    return "", "Automatic detection unavailable"


def _cname_target():
    configured = _clean_hostname(getattr(settings, "EDUMANAGE_CNAME_TARGET", ""))
    if configured:
        return configured
    candidates = _origin_host_candidates()
    return candidates[0] if candidates else DEFAULT_CNAME_TARGET


def get_dns_targets():
    configured_ip = _clean_public_ipv4(
        getattr(settings, "EDUMANAGE_PUBLIC_IPV4", "")
    )
    if configured_ip:
        public_ip = configured_ip
        source = "Configured by EDUMANAGE_PUBLIC_IPV4"
    else:
        public_ip, source = _auto_detect_public_ipv4()

    return {
        "a_record_target": public_ip or A_RECORD_PLACEHOLDER,
        "a_record_ready": bool(public_ip),
        "a_record_source": source,
        "cname_target": _cname_target(),
    }
