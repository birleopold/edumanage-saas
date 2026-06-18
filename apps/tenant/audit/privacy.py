from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .models import ConsentRecord
from .services import client_ip, user_agent


class PrivacyAcceptanceGuard:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            if getattr(request, "user", None) and request.user.is_authenticated:
                exempt = ["/privacy/accept/", "/logout/", "/static/", "/media/", "/api/"]
                if not any(request.path.startswith(x) for x in exempt):
                    version = getattr(settings, "PRIVACY_POLICY_VERSION", "1.0")
                    accepted = ConsentRecord.objects.filter(user=request.user, consent_type=ConsentRecord.PRIVACY, accepted=True, version=version).exists()
                    if not accepted:
                        return redirect("audit_privacy_accept")
        except Exception:
            pass
        return self.get_response(request)


@login_required
def accept_privacy(request):
    version = getattr(settings, "PRIVACY_POLICY_VERSION", "1.0")
    if request.method == "POST":
        ConsentRecord.objects.create(user=request.user, consent_type=ConsentRecord.PRIVACY, accepted=True, version=version, ip_address=client_ip(request), user_agent=user_agent(request), note="Accepted privacy policy in portal")
        messages.success(request, "Privacy policy accepted.")
        return redirect("admin_home")
    return render(request, "portals/audit/privacy_accept.html", {"version": version})
