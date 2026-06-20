from django.shortcuts import render

from apps.tenant.portals.permissions import admin_portal_required

from .models import AssetAssignment, InventoryItem, StockMovement


@admin_portal_required
def inventory_dashboard(request):
    recent_items = InventoryItem.objects.order_by("-created_at")[:8]
    recent_movements = StockMovement.objects.select_related("item", "created_by").order_by("-created_at")[:8]
    recent_assignments = AssetAssignment.objects.select_related(
        "item", "assigned_to_user", "assigned_to_student"
    ).order_by("-created_at")[:8]

    low_stock_count = 0
    for item in InventoryItem.objects.filter(is_active=True)[:500]:
        try:
            if item.stock_on_hand() <= 10:
                low_stock_count += 1
        except Exception:
            pass

    context = {
        "item_count": InventoryItem.objects.count(),
        "active_item_count": InventoryItem.objects.filter(is_active=True).count(),
        "movement_count": StockMovement.objects.count(),
        "assignment_count": AssetAssignment.objects.count(),
        "low_stock_count": low_stock_count,
        "recent_items": recent_items,
        "recent_movements": recent_movements,
        "recent_assignments": recent_assignments,
    }
    return render(request, "portals/admin/inventory/dashboard.html", context)
