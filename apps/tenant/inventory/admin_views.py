from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.campus_permissions import get_user_campus_scope
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.users.models import Role

from .forms import AssetAssignmentForm, InventoryItemForm, StockMovementForm
from .models import AssetAssignment, InventoryItem, StockMovement


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = request.GET.get("per_page")
    per_page = default
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = default
    return max(1, min(per_page, max_value))


def _asset_assignment_queryset_for(user):
    qs = AssetAssignment.objects.select_related(
        "item",
        "assigned_to_user",
        "assigned_to_student",
        "assigned_to_student__campus",
        "created_by",
    )
    scoped = get_user_campus_scope(user)
    if scoped:
        qs = qs.filter(Q(assigned_to_student__campus=scoped) | Q(assigned_to_student__isnull=True))
    return qs


@admin_portal_required
def item_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = InventoryItem.objects.all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(unit__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    items = list(page_obj.object_list)
    for it in items:
        it._stock_on_hand = it.stock_on_hand()

    return render(
        request,
        "portals/admin/inventory/items_list.html",
        {"items": items, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@admin_portal_required
def item_create(request):
    if request.method == "POST":
        form = InventoryItemForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Item created.")
            return redirect("admin_inventory_items_list")
    else:
        form = InventoryItemForm()

    return render(request, "portals/admin/inventory/item_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def item_edit(request, pk: int):
    obj = get_object_or_404(InventoryItem, pk=pk)

    if request.method == "POST":
        form = InventoryItemForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Item updated.")
            return redirect("admin_inventory_items_list")
    else:
        form = InventoryItemForm(instance=obj)

    return render(
        request,
        "portals/admin/inventory/item_form.html",
        {"form": form, "mode": "edit", "item": obj},
    )


@admin_portal_required
def movement_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = StockMovement.objects.select_related("item", "created_by").all()
    if q:
        qs = qs.filter(Q(item__name__icontains=q) | Q(item__sku__icontains=q) | Q(reference__icontains=q) | Q(note__icontains=q))

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/inventory/movements_list.html",
        {"movements": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@admin_portal_required
def movement_create(request):
    if request.method == "POST":
        form = StockMovementForm(request.POST)
        if form.is_valid():
            mv = form.save(commit=False)
            mv.created_by = request.user
            mv.save()
            messages.success(request, "Movement recorded.")
            return redirect("admin_inventory_movements_list")
    else:
        form = StockMovementForm()

    return render(request, "portals/admin/inventory/movement_form.html", {"form": form})


@admin_portal_required
def assignment_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs = _asset_assignment_queryset_for(request.user)

    if q:
        qs = qs.filter(
            Q(item__name__icontains=q)
            | Q(item__sku__icontains=q)
            | Q(assigned_to_student__first_name__icontains=q)
            | Q(assigned_to_student__last_name__icontains=q)
            | Q(assigned_to_student__student_id__icontains=q)
            | Q(assigned_to_user__username__icontains=q)
            | Q(note__icontains=q)
        )

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "portals/admin/inventory/assignments_list.html",
        {"assignments": page_obj.object_list, "page_obj": page_obj, "q": q, "per_page": per_page},
    )


@admin_portal_required
def assignment_create(request):
    scoped = get_user_campus_scope(request.user)
    if request.method == "POST":
        form = AssetAssignmentForm(request.POST, campus_scope=scoped)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            messages.success(request, "Assignment created.")
            return redirect("admin_inventory_assignments_list")
    else:
        form = AssetAssignmentForm(campus_scope=scoped)

    return render(request, "portals/admin/inventory/assignment_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def assignment_edit(request, pk: int):
    scoped = get_user_campus_scope(request.user)
    obj = get_object_or_404(_asset_assignment_queryset_for(request.user), pk=pk)

    if request.method == "POST":
        form = AssetAssignmentForm(request.POST, instance=obj, campus_scope=scoped)
        if form.is_valid():
            form.save()
            messages.success(request, "Assignment updated.")
            return redirect("admin_inventory_assignments_list")
    else:
        form = AssetAssignmentForm(instance=obj, campus_scope=scoped)

    return render(
        request,
        "portals/admin/inventory/assignment_form.html",
        {"form": form, "mode": "edit", "assignment": obj},
    )
