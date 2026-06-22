from .portal_services import polls_for_user


def dashboard_polls(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    try:
        return {"poll_dashboard_items": list(polls_for_user(request)[:3])}
    except Exception:
        return {"poll_dashboard_items": []}
