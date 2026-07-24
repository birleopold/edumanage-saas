from django import template

from apps.public.tenants.dns_targets import get_dns_targets


register = template.Library()


@register.simple_tag
def platform_dns_target(record_type):
    targets = get_dns_targets()
    if str(record_type or "").upper() == "A":
        return targets["a_record_target"]
    return targets["cname_target"]
