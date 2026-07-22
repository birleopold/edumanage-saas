import base64

from cryptography.hazmat.primitives import serialization
from django.core.management.base import BaseCommand
from py_vapid import Vapid


def base64url_no_padding(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


class Command(BaseCommand):
    help = "Generate VAPID keys for EduManage PWA browser push notifications."

    def add_arguments(self, parser):
        parser.add_argument(
            "--subject",
            default="mailto:support@edumanage.local",
            help="Contact subject used in VAPID claims, usually mailto:admin@example.com.",
        )

    def handle(self, *args, **options):
        vapid = Vapid()
        vapid.generate_keys()

        public_raw = vapid.public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        private_pem = vapid.private_pem().decode("ascii").strip()
        escaped_private_pem = private_pem.replace("\n", r"\n")

        self.stdout.write("# Add these values to your environment or .env file:")
        self.stdout.write(f"WEB_PUSH_PUBLIC_KEY={base64url_no_padding(public_raw)}")
        self.stdout.write(f"WEB_PUSH_PRIVATE_KEY={escaped_private_pem}")
        self.stdout.write(f"WEB_PUSH_SUBJECT={options['subject']}")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Generated VAPID keys for PWA push notifications."))
