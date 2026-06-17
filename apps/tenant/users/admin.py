from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import MobileDevice, Role, User, UserRole


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    pass


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "created_at")
    search_fields = ("user__username", "user__email", "role__code")


@admin.register(MobileDevice)
class MobileDeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "platform", "device_id", "app_version", "is_active", "last_seen_at")
    list_filter = ("platform", "is_active")
    search_fields = ("user__username", "user__email", "device_id", "push_token")
    date_hierarchy = "last_seen_at"
