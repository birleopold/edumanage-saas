from django.core.management.base import BaseCommand

from apps.tenant.parents.digest import send_all_parent_digests


class Command(BaseCommand):
    help = "Send weekly Smart Parent Digest notifications to active parents."

    def add_arguments(self, parser):
        parser.add_argument("--no-push", action="store_true", help="Create portal notifications without sending PWA push alerts.")
        parser.add_argument("--email", action="store_true", help="Also email each digest to the parent email address.")
        parser.add_argument("--whatsapp", action="store_true", help="Also send each digest by WhatsApp when parents have consented.")
        parser.add_argument("--whatsapp-dry-run", action="store_true", help="Create WhatsApp outbound logs without contacting the provider.")
        parser.add_argument("--force", action="store_true", help="Resend even if a digest already exists for the parent and window.")
        parser.add_argument("--ignore-parent-preferences", action="store_true", help="Use command channel flags instead of each parent's digest preferences.")
        parser.add_argument("--include-inactive", action="store_true", help="Include inactive parent profiles.")

    def handle(self, *args, **options):
        result = send_all_parent_digests(
            include_push=not options["no_push"],
            include_email=options["email"],
            include_whatsapp=options["whatsapp"],
            whatsapp_dry_run=options["whatsapp_dry_run"],
            force=options["force"],
            use_parent_preferences=not options["ignore_parent_preferences"],
            active_only=not options["include_inactive"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Parent digests complete: {result['sent']} sent, {result['skipped']} skipped, "
                f"{result['duplicates']} duplicate(s), {result['push_sent']} PWA alert(s), "
                f"{result['email_sent']} email(s), {result['whatsapp_sent']} WhatsApp message(s)."
            )
        )
