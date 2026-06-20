from django.urls import path

from . import admin_views, dashboard_views

urlpatterns = [
    path("", dashboard_views.inventory_dashboard, name="admin_inventory_dashboard"),
    path("items/", admin_views.item_list, name="admin_inventory_items_list"),
    path("items/create/", admin_views.item_create, name="admin_inventory_items_create"),
    path("items/<int:pk>/edit/", admin_views.item_edit, name="admin_inventory_items_edit"),
    path("movements/", admin_views.movement_list, name="admin_inventory_movements_list"),
    path("movements/create/", admin_views.movement_create, name="admin_inventory_movements_create"),
    path("assignments/", admin_views.assignment_list, name="admin_inventory_assignments_list"),
    path("assignments/create/", admin_views.assignment_create, name="admin_inventory_assignments_create"),
    path("assignments/<int:pk>/edit/", admin_views.assignment_edit, name="admin_inventory_assignments_edit"),
]
