from django.core.exceptions import PermissionDenied

from apps.tenant.orgsettings.services import set_current_campus
from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.portals.role_navigation import is_global_admin_user
from apps.tenant.users.models import Role

from . import promotion_views


@admin_portal_required
def stream_promotion(request):
    if is_global_admin_user(request.user):
        return promotion_views.stream_promotion(request)

    if request.user.has_role(Role.CAMPUS_ADMIN):
        scope = get_user_campus_scope(request.user)
        if scope is None:
            raise PermissionDenied("Your Campus Admin account has no active campus assignment.")
        set_current_campus(request, scope)

    return promotion_views.stream_promotion(request)
