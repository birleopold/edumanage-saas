import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow

from .models import FederatedIdentity, User
from apps.tenant.portals.role_navigation import portal_home_url_for


SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"]


def _enabled():
    return bool(getattr(settings, "GOOGLE_OAUTH_ENABLED", False) and settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)


def _redirect_uri(request):
    return request.build_absolute_uri(reverse("google_oauth_callback"))


def _flow(request, *, state=None):
    config = {
        "web": {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    return Flow.from_client_config(config, scopes=SCOPES, state=state, redirect_uri=_redirect_uri(request))


def google_login_start(request):
    if not _enabled():
        messages.error(request, "Google sign-in is not enabled for this school.")
        return redirect("login")
    flow = _flow(request)
    authorization_url, state = flow.authorization_url(
        access_type="online",
        include_granted_scopes="true",
        prompt="select_account",
    )
    request.session["google_oauth_state"] = state
    request.session["google_oauth_nonce"] = secrets.token_urlsafe(24)
    return redirect(authorization_url)


def google_login_callback(request):
    expected_state = request.session.pop("google_oauth_state", None)
    if not expected_state or request.GET.get("state") != expected_state:
        messages.error(request, "Google sign-in could not be verified. Please try again.")
        return redirect("login")
    if request.GET.get("error"):
        messages.error(request, "Google sign-in was cancelled or denied.")
        return redirect("login")

    flow = _flow(request, state=expected_state)
    flow.fetch_token(authorization_response=request.build_absolute_uri())
    credentials = flow.credentials
    claims = id_token.verify_oauth2_token(
        credentials.id_token,
        google_requests.Request(),
        settings.GOOGLE_OAUTH_CLIENT_ID,
    )
    if claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        messages.error(request, "Google identity issuer was not accepted.")
        return redirect("login")
    email = (claims.get("email") or "").strip().lower()
    subject = (claims.get("sub") or "").strip()
    if not subject or not email or claims.get("email_verified") is not True:
        messages.error(request, "Google did not provide a verified email address.")
        return redirect("login")

    identity = FederatedIdentity.objects.select_related("user").filter(provider=FederatedIdentity.GOOGLE, subject=subject).first()
    if identity:
        user = identity.user
    else:
        matches = list(User.objects.filter(email__iexact=email, is_active=True)[:2])
        if len(matches) != 1:
            messages.error(request, "This Google account is not linked to an active EduManage account. Use your school credentials first or contact the school.")
            return redirect("login")
        user = matches[0]
        FederatedIdentity.objects.create(
            user=user,
            provider=FederatedIdentity.GOOGLE,
            subject=subject,
            email=email,
            email_verified=True,
            last_login_at=timezone.now(),
        )

    if not user.is_active:
        messages.error(request, "This EduManage account is inactive.")
        return redirect("login")
    identity = FederatedIdentity.objects.filter(provider=FederatedIdentity.GOOGLE, subject=subject).first()
    if identity:
        identity.email = email
        identity.email_verified = True
        identity.last_login_at = timezone.now()
        identity.save(update_fields=["email", "email_verified", "last_login_at"])
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect(portal_home_url_for(user))


@login_required
def google_link_start(request):
    if not _enabled():
        messages.error(request, "Google sign-in is not enabled.")
        return redirect("user_profile")
    request.session["google_link_user_id"] = request.user.pk
    return google_login_start(request)
