from django.db import migrations, models
import django.utils.timezone
class Migration(migrations.Migration):
 dependencies=[("tenants","0008_platformstaffaccess")]
 operations=[migrations.CreateModel(name="PlatformBackupRecord",fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("status",models.CharField(choices=[("SUCCESS","Success"),("FAILED","Failed"),("RESTORE_TESTED","Restore tested")],max_length=24)),("backup_scope",models.CharField(default="postgresql",max_length=120)),("location_label",models.CharField(blank=True,max_length=255)),("checksum",models.CharField(blank=True,max_length=128)),("notes",models.TextField(blank=True)),("occurred_at",models.DateTimeField(db_index=True,default=django.utils.timezone.now)),("recorded_at",models.DateTimeField(auto_now_add=True))],options={"ordering":("-occurred_at",)})]
