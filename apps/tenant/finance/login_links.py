import uuid

from django.http import JsonResponse
from django.shortcuts import redirect

from .integration_services import sso_authorization_url


def external_login_start(request, provider_type):
    state = uuid.uuid4().hex
    request.session["external_login_state"] = state
    try:
        url = sso_authorization_url(provider_type.upper(), request.build_absolute_uri("/external-login/callback/"), state)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    return redirect(url)


def external_login_callback(request):
    return JsonResponse({"ok": True, "code_received": bool(request.GET.get("code"))})
