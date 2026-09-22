from django.shortcuts import render
from django.db.models import Q

from apps.tenant.portals.campus_permissions import get_accessible_campuses
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.users.models import Role

from .models import AssetAssignment, InventoryItem, StockMovement


@admin_portal_required
def inventory_dashboard(request):
    scoped = get_accessible_campuses(request.user)
    assignment_qs = AssetAssignment.objects.select_related(
        "item", "assigned_to_user", "assigned_to_student", "assigned_to_student__campus"
    )
    if not request.user.is_superuser and not request.user.has_role(Role.ADMIN) and not request.user.has_role(Role.PRINCIPAL):
        assignment_qs = assignment_qs.filter(
            Q(assigned_to_student__campus__in=scoped)
            | Q(assigned_to_student__isnull=True)
        )

    recent_items = InventoryItem.objects.order_by("-created_at")[:8]
    recent_movements = StockMovement.objects.select_related("item", "created_by").order_by("-created_at")[:8]
    recent_assignments = assignment_qs.order_by("-created_at")[:8]

    low_stock_count = InventoryItem.objects.filter(
        is_active=True, cached_stock_on_hand__lte=10
    ).count()

    context = {
        "item_count": InventoryItem.objects.count(),
        "active_item_count": InventoryItem.objects.filter(is_active=True).count(),
        "movement_count": StockMovement.objects.count(),
        "assignment_count": assignment_qs.count(),
        "low_stock_count": low_stock_count,
        "recent_items": recent_items,
        "recent_movements": recent_movements,
        "recent_assignments": recent_assignments,
    }
    return render(request, "portals/admin/inventory/dashboard.html", context)
