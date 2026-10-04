from django.db import migrations, models

def classify_existing_internal(apps, schema_editor):
    Tenant=apps.get_model("tenants","Tenant")
    Tenant.objects.filter(schema_name__in=["public","demo","johnathan_schools"]).update(is_internal=True)

class Migration(migrations.Migration):
    dependencies=[("tenants","0010_platform_audit_hashes")]
    operations=[
        migrations.AddField(model_name="tenant",name="is_internal",field=models.BooleanField(db_index=True,default=False,help_text="Internal/demo tenants are excluded from customer billing automation.")),
        migrations.RunPython(classify_existing_internal,migrations.RunPython.noop),
    ]
