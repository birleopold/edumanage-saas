from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Role, User, UserRole


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
