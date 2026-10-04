from django.db import connection
from apps.public.tenants.models import TenantSubscription

def current_subscription():
    schema=getattr(connection,"schema_name","")
    if not schema or schema=="public": return None
    return TenantSubscription.objects.filter(tenant__schema_name=schema).select_related("plan").first()

def quota_allows(resource, additional=1):
    sub=current_subscription()
    if not sub or not sub.is_usable: return True, ""
    field={"students":"max_students","staff":"max_staff","campuses":"max_campuses"}[resource]
    limit=getattr(sub.plan,field,0)
    if not limit: return True, ""
    if resource=="students":
        from apps.tenant.students.models import StudentProfile; used=StudentProfile.objects.filter(is_active=True).count()
    elif resource=="staff":
        from apps.tenant.teachers.models import TeacherProfile; used=TeacherProfile.objects.filter(is_active=True).count()
    else:
        from apps.tenant.orgsettings.models import Campus; used=Campus.objects.filter(is_active=True).count()
    if used+additional>limit: return False, f"Your {sub.plan.name} plan allows {limit} {resource}. Current usage is {used}."
    return True, ""
