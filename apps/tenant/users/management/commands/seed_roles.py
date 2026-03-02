from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.tenant.users.models import Role, UserRole


class Command(BaseCommand):
    help = "Seed default roles and optionally assign ADMIN role to a user."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            dest="username",
            default=None,
            help="Username to assign ADMIN role to. If omitted, assigns to first superuser if found.",
        )
        parser.add_argument(
            "--no-assign",
            action="store_true",
            help="Only create roles; do not assign ADMIN role.",
        )

    def handle(self, *args, **options):
        created_count = 0
        for code, label in Role.CODE_CHOICES:
            _, created = Role.objects.get_or_create(code=code, defaults={"name": label})
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Roles ensured. Newly created: {created_count}"))

        if options.get("no_assign"):
            return

        username = options.get("username")
        User = get_user_model()

        user = None
        if username:
            user = User.objects.filter(username=username).first()
            if not user:
                self.stdout.write(self.style.WARNING(f"User '{username}' not found; skipping assignment."))
                return
        else:
            user = User.objects.filter(is_superuser=True).order_by("id").first()
            if not user:
                self.stdout.write(self.style.WARNING("No superuser found; skipping assignment."))
                return

        admin_role = Role.objects.get(code=Role.ADMIN)
        UserRole.objects.get_or_create(user=user, role=admin_role)
        self.stdout.write(self.style.SUCCESS(f"Assigned ADMIN role to '{user.get_username()}'."))
