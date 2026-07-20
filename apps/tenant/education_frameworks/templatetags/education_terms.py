from django import template

from apps.tenant.education_frameworks.integration import (
    external_exam_aliases_for_request,
    framework_aliases_for_request,
    terminology_for_request,
)


register = template.Library()


def _request_from_context(context):
    return context.get("request") if context is not None else None


@register.simple_tag(takes_context=True)
def education_term(
    context,
    key: str,
    default: str = "",
    stage_code: str = "",
) -> str:
    terms = terminology_for_request(
        _request_from_context(context),
        stage_code=stage_code or None,
    )
    fallback = default or str(key).replace("_", " ").title()
    return str(terms.get(key, fallback))


@register.simple_tag(takes_context=True)
def education_alias(context, code: str, default: str = "") -> str:
    aliases = framework_aliases_for_request(
        _request_from_context(context)
    )
    return str(aliases.get(code, default or code))


@register.simple_tag(takes_context=True)
def external_exam_aliases(context) -> str:
    return ", ".join(
        external_exam_aliases_for_request(
            _request_from_context(context)
        )
    )


@register.simple_tag(takes_context=True)
def education_terms(context, stage_code: str = "") -> dict[str, str]:
    return terminology_for_request(
        _request_from_context(context),
        stage_code=stage_code or None,
    )
