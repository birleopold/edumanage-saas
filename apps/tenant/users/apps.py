from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenant.users"
    label = "users"

    def ready(self):
        from .passwords import install_user_manager_password_compatibility

        install_user_manager_password_compatibility()
