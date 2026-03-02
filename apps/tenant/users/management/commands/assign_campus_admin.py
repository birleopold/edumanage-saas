"""
Management command to assign campus admin role to users.
"""
from django.core.management.base import BaseCommand

from apps.tenant.orgsettings.models import Campus
from apps.tenant.users.models import Role, User, UserRole


class Command(BaseCommand):
    help = "Assign campus admin role to a user for a specific campus"

    def add_arguments(self, parser):
        parser.add_argument(
            'username',
            type=str,
            help='Username of the user to assign campus admin role'
        )
        parser.add_argument(
            'campus_id',
            type=int,
            help='ID of the campus to assign admin rights for'
        )
        parser.add_argument(
            '--remove',
            action='store_true',
            help='Remove campus admin role instead of adding it'
        )

    def handle(self, *args, **options):
        username = options['username']
        campus_id = options['campus_id']
        remove = options.get('remove', False)

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"User '{username}' not found")
            )
            return

        try:
            campus = Campus.objects.get(id=campus_id)
        except Campus.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Campus with ID {campus_id} not found")
            )
            return

        campus_admin_role, _ = Role.objects.get_or_create(
            code=Role.CAMPUS_ADMIN,
            defaults={'name': 'Campus Admin'}
        )

        if remove:
            deleted_count, _ = UserRole.objects.filter(
                user=user,
                role=campus_admin_role,
                campus=campus
            ).delete()
            
            if deleted_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Removed campus admin role for '{username}' on campus '{campus.name}'"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"User '{username}' was not a campus admin for '{campus.name}'"
                    )
                )
        else:
            user_role, created = UserRole.objects.get_or_create(
                user=user,
                role=campus_admin_role,
                campus=campus
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Assigned campus admin role to '{username}' for campus '{campus.name}'"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"User '{username}' is already a campus admin for '{campus.name}'"
                    )
                )

        # Show current campus admin assignments for this user
        self.stdout.write("\nCurrent campus admin assignments for this user:")
        campus_roles = UserRole.objects.filter(
            user=user,
            role__code=Role.CAMPUS_ADMIN
        ).select_related('campus')
        
        if campus_roles.exists():
            for ur in campus_roles:
                self.stdout.write(f"  - {ur.campus.name} (ID: {ur.campus.id})")
        else:
            self.stdout.write("  (none)")
