from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def format_money_amount(amount, currency_code: str = "UGX"):
    """
    Format a numeric amount with a currency code for display (e.g. invoices).
    Usage: {{ amount|format_money_amount:org_profile.default_currency }}
    """
    if amount is None:
        return "—"
    code = (currency_code or "UGX").strip().upper() or "UGX"
    try:
        val = Decimal(str(amount))
    except Exception:
        return str(amount)
    if code == "UGX":
        return f"{code} {val:,.0f}"
    return f"{code} {val:,.2f}"


@register.filter
def get_item(mapping, key):
    if mapping is None:
        return None
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.simple_tag
def page_with_query(request, page_number):
    """
    Build a pagination URL preserving active query parameters.
    """
    if not request:
        return f"?page={page_number}"
    query_params = request.GET.copy()
    query_params["page"] = page_number
    return f"?{query_params.urlencode()}"
