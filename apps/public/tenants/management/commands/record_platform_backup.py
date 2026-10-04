from django.core.management.base import BaseCommand
from apps.public.tenants.models import PlatformBackupRecord
class Command(BaseCommand):
 help="Record external PostgreSQL backup or restore-test evidence."
 def add_arguments(self,p):
  p.add_argument("--status",required=True,choices=[x[0] for x in PlatformBackupRecord.STATUS_CHOICES]); p.add_argument("--location",default=""); p.add_argument("--checksum",default=""); p.add_argument("--notes",default="")
 def handle(self,*a,**o):
  r=PlatformBackupRecord.objects.create(status=o["status"],location_label=o["location"],checksum=o["checksum"],notes=o["notes"])
  self.stdout.write(self.style.SUCCESS(f"Backup evidence #{r.pk}: {r.status}"))
