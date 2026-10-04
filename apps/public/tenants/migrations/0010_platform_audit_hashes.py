from django.db import migrations, models
class Migration(migrations.Migration):
 dependencies=[("tenants","0009_platformbackuprecord")]
 operations=[migrations.AddField(model_name="platformauditevent",name="previous_hash",field=models.CharField(blank=True,max_length=64)),migrations.AddField(model_name="platformauditevent",name="event_hash",field=models.CharField(blank=True,db_index=True,max_length=64))]
