from functools import wraps

from django.http import HttpResponseForbidden

from .services import can_user_export, log_audit


def export_permission_required(module, action="export"):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not can_user_export(request.user, module, action=action):
                log_audit(request, action="EXPORT", metadata={"module": module, "blocked": True, "required_action": action})
                return HttpResponseForbidden("You do not have permission for this export/print/download.")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
