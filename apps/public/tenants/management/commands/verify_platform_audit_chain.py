import hashlib, json
from django.core.management.base import BaseCommand, CommandError
from apps.public.tenants.models import PlatformAuditEvent
class Command(BaseCommand):
 help="Verify the tamper-evident chain for hashed Platform audit events."
 def handle(self,*a,**o):
  previous=""
  checked=0
  for e in PlatformAuditEvent.objects.order_by("id"):
   if not e.event_hash: continue
   payload={"action":e.action,"actor_id":e.actor_id,"tenant_id":e.tenant_id,"domain_id":e.domain_id,"object_label":e.object_label,"before":e.before or {},"after":e.after or {},"metadata":e.metadata or {},"previous_hash":e.previous_hash}
   expected=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
   if e.previous_hash!=previous or e.event_hash!=expected: raise CommandError(f"Platform audit chain failed at event {e.pk}")
   previous=e.event_hash; checked+=1
  self.stdout.write(self.style.SUCCESS(f"Platform audit chain valid: {checked} hashed event(s)."))
