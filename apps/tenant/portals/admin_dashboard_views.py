"""
Enhanced admin dashboard with campus metrics.
"""
from django.shortcuts import render

from apps.tenant.orgsettings.campus_dashboard import (
    get_all_campuses_summary,
    get_campus_metrics,
)
from apps.tenant.orgsettings.services import (
    campus_queryset,
    get_current_campus,
    selected_campus_id_from_request,
    update_current_campus_from_request,
)
from apps.tenant.portals.campus_permissions import (
    get_accessible_campuses,
    get_user_campus_scope,
)
from apps.tenant.portals.permissions import admin_portal_required


@admin_portal_required
def admin_dashboard(request):
    """
    Enhanced admin dashboard with campus-aware metrics.
    """
    update_current_campus_from_request(request)
    
    # Get user's accessible campuses
    accessible_campuses = get_accessible_campuses(request.user)
    user_campus_scope = get_user_campus_scope(request.user)
    
    # Get selected campus
    selected_campus_id = selected_campus_id_from_request(request)
    current_campus = get_current_campus(request)
    
    # Determine what to show
    if selected_campus_id:
        # Show specific campus metrics
        campus = accessible_campuses.filter(id=selected_campus_id).first()
        if campus:
            metrics = get_campus_metrics(campus, date_range_days=30)
            view_mode = 'single_campus'
        else:
            # User doesn't have access to this campus
            metrics = None
            view_mode = 'no_access'
    else:
        # Show all campuses summary (only for global admins)
        if user_campus_scope:
            # Campus admin must select a campus
            metrics = None
            view_mode = 'select_campus'
        else:
            # Global admin viewing all campuses
            metrics = get_all_campuses_summary()
            view_mode = 'all_campuses'
    
    context = {
        'campuses': accessible_campuses,
        'selected_campus_id': selected_campus_id,
        'current_campus': current_campus,
        'user_campus_scope': user_campus_scope,
        'metrics': metrics,
        'view_mode': view_mode,
    }
    
    return render(request, 'portals/admin/dashboard.html', context)
