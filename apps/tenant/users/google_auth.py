import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django_tenants.utils import schema_context

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow

from apps.public.tenants.models import Domain, GoogleLoginHandoff, GoogleOAuthTransaction
from apps.tenant.portals.role_navigation import portal_home_url_for
from .models import FederatedIdentity, User


SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"]


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _enabled():
    return bool(getattr(settings, "GOOGLE_OAUTH_ENABLED", False) and settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)


def _central_callback_uri():
    return getattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", "").strip()


def _flow(*, state=None):
    config = {"web": {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }}
    return Flow.from_client_config(config, scopes=SCOPES, state=state, redirect_uri=_central_callback_uri())


def google_login_start(request):
    if not _enabled() or not _central_callback_uri():
        messages.error(request, "Google sign-in is not enabled for this school.")
        return redirect("login")

    hostname = request.get_host().split(":", 1)[0].lower()
    domain = Domain.objects.select_related("tenant").filter(domain__iexact=hostname).first()
    if not domain or domain.tenant.schema_name in {"public", ""}:
        messages.error(request, "This school domain is not registered for Google sign-in.")
        return redirect("login")
    if getattr(domain.tenant, "status", "active").lower() not in {"active", "trialing"}:
        messages.error(request, "This school is not currently available for Google sign-in.")
        return redirect("login")

    raw_state = secrets.token_urlsafe(32)
    GoogleOAuthTransaction.objects.create(
        state_digest=_digest(raw_state),
        tenant=domain.tenant,
        return_domain=domain,
        expires_at=timezone.now() + timedelta(minutes=getattr(settings, "GOOGLE_OAUTH_TRANSACTION_MINUTES", 10)),
    )
    flow = _flow(state=raw_state)
    authorization_url, _ = flow.authorization_url(
        access_type="online",
        include_granted_scopes="true",
        prompt="select_account",
    )
    return redirect(authorization_url)


def google_login_callback(request):
    raw_state = request.GET.get("state", "")
    if not raw_state:
        return redirect("/?google_auth=invalid_state")

    with transaction.atomic():
        oauth_tx = (
            GoogleOAuthTransaction.objects.select_for_update()
            .select_related("tenant", "return_domain")
            .filter(state_digest=_digest(raw_state))
            .first()
        )
        if not oauth_tx or not oauth_tx.is_valid():
            return redirect("/?google_auth=invalid_state")
        # Consume before external token exchange so a state cannot be replayed.
        oauth_tx.used_at = timezone.now()
        oauth_tx.save(update_fields=["used_at"])

    if request.GET.get("error"):
        return redirect(f"https://{oauth_tx.return_domain.domain}/login/?google_auth=cancelled")

    flow = _flow(state=raw_state)
    flow.fetch_token(authorization_response=request.build_absolute_uri())
    claims = id_token.verify_oauth2_token(flow.credentials.id_token, google_requests.Request(), settings.GOOGLE_OAUTH_CLIENT_ID)
    if claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        return redirect(f"https://{oauth_tx.return_domain.domain}/login/?google_auth=invalid_identity")
    email = (claims.get("email") or "").strip().lower()
    subject = (claims.get("sub") or "").strip()
    if not subject or not email or claims.get("email_verified") is not True:
        return redirect(f"https://{oauth_tx.return_domain.domain}/login/?google_auth=unverified_email")

    raw_handoff = secrets.token_urlsafe(32)
    GoogleLoginHandoff.objects.create(
        token_digest=_digest(raw_handoff),
        tenant=oauth_tx.tenant,
        return_domain=oauth_tx.return_domain,
        google_subject=subject,
        verified_email=email,
        expires_at=timezone.now() + timedelta(minutes=getattr(settings, "GOOGLE_OAUTH_HANDOFF_MINUTES", 2)),
    )
    return redirect(f"https://{oauth_tx.return_domain.domain}/auth/google/complete/?token={raw_handoff}")


def google_login_complete(request):
    raw_token = request.GET.get("token", "")
    if not raw_token:
        messages.error(request, "Google sign-in handoff is missing.")
        return redirect("login")
    hostname = request.get_host().split(":", 1)[0].lower()

    with transaction.atomic():
        handoff = (
            GoogleLoginHandoff.objects.select_for_update()
            .select_related("tenant", "return_domain")
            .filter(token_digest=_digest(raw_token))
            .first()
        )
        if not handoff or not handoff.is_valid() or handoff.return_domain.domain.lower() != hostname:
            messages.error(request, "Google sign-in handoff is invalid or expired.")
            return redirect("login")
        handoff.used_at = timezone.now()
        handoff.save(update_fields=["used_at"])

    # The tenant middleware already selected this schema from the hostname.
    # Re-check it to make the handoff incapable of crossing tenants.
    request_tenant = getattr(request, "tenant", None)
    if not request_tenant or request_tenant.schema_name != handoff.tenant.schema_name:
        messages.error(request, "Google sign-in tenant verification failed.")
        return redirect("login")

    identity = FederatedIdentity.objects.select_related("user").filter(provider=FederatedIdentity.GOOGLE, subject=handoff.google_subject).first()
    if identity:
        user = identity.user
    else:
        matches = list(User.objects.filter(email__iexact=handoff.verified_email, is_active=True)[:2])
        if len(matches) != 1:
            messages.error(request, "This Google account is not linked to an active EduManage account. Use your school credentials or contact the school.")
            return redirect("login")
        user = matches[0]
        identity = FederatedIdentity.objects.create(
            user=user, provider=FederatedIdentity.GOOGLE, subject=handoff.google_subject,
            email=handoff.verified_email, email_verified=True,
        )

    if not user.is_active:
        messages.error(request, "This EduManage account is inactive.")
        return redirect("login")
    identity.email = handoff.verified_email
    identity.email_verified = True
    identity.last_login_at = timezone.now()
    identity.save(update_fields=["email", "email_verified", "last_login_at"])
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect(portal_home_url_for(user))
