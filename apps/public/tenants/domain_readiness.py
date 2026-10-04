import socket
import ssl
from urllib.request import Request, urlopen
from urllib.error import URLError

from django.utils import timezone

from .dns_targets import get_dns_targets


def inspect_domain(domain):
    targets = get_dns_targets()
    expected_ip = targets["a_record_target"] if targets["a_record_ready"] else ""
    expected_cname = targets["cname_target"].rstrip(".").lower()
    resolved_ips = set()
    try:
        for item in socket.getaddrinfo(domain.domain, 443, family=socket.AF_INET, type=socket.SOCK_STREAM):
            resolved_ips.add(item[4][0])
    except OSError:
        pass

    dns_ok = bool(expected_ip and expected_ip in resolved_ips)
    cname_hint = False
    try:
        canonical = socket.getfqdn(domain.domain).rstrip(".").lower()
        cname_hint = canonical == expected_cname
    except OSError:
        canonical = ""

    https_ok = False
    https_error = ""
    try:
        req = Request(f"https://{domain.domain}/health/", headers={"User-Agent": "EduManage-Domain-Readiness/1.0"})
        context = ssl.create_default_context()
        with urlopen(req, timeout=6, context=context) as response:
            https_ok = 200 <= response.status < 500
    except Exception as exc:
        https_error = str(exc)[:240]

    return {
        "dns_ok": dns_ok or cname_hint,
        "resolved_ips": sorted(resolved_ips),
        "expected_ip": expected_ip,
        "expected_cname": expected_cname,
        "https_ok": https_ok,
        "https_error": https_error,
        "checked_at": timezone.now(),
    }
