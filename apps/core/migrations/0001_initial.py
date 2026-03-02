# Generated migration for core app models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('students', '0002_studentprofile_campus'),
        ('orgsettings', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='StatusHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_id', models.PositiveIntegerField()),
                ('old_status', models.CharField(blank=True, max_length=64)),
                ('new_status', models.CharField(max_length=64)),
                ('reason', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('changed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='status_changes', to=settings.AUTH_USER_MODEL)),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
            ],
            options={
                'verbose_name_plural': 'Status histories',
                'ordering': ('-created_at',),
            },
        ),
        migrations.CreateModel(
            name='ActionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_id', models.PositiveIntegerField()),
                ('action', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
                ('performed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='performed_actions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('audience', models.CharField(choices=[('ALL', 'All Users'), ('ADMIN', 'Administrators'), ('CAMPUS_ADMIN', 'Campus Admins'), ('TEACHERS', 'Teachers'), ('STUDENTS', 'Students'), ('PARENTS', 'Parents'), ('STAFF', 'Staff')], default='ALL', help_text='Target audience for broadcast notifications', max_length=16)),
                ('title', models.CharField(max_length=200)),
                ('message', models.TextField()),
                ('priority', models.CharField(choices=[('NORMAL', 'Normal'), ('URGENT', 'Urgent'), ('CRITICAL', 'Critical')], default='NORMAL', max_length=16)),
                ('link', models.CharField(blank=True, help_text='Optional link to related page', max_length=255)),
                ('is_read', models.BooleanField(default=False)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('campus', models.ForeignKey(blank=True, help_text='Campus-specific notification', null=True, on_delete=django.db.models.deletion.CASCADE, to='orgsettings.campus')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_notifications', to=settings.AUTH_USER_MODEL)),
                ('recipient', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
        migrations.CreateModel(
            name='InventoryItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sku', models.CharField(blank=True, help_text='Stock Keeping Unit', max_length=64)),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('category', models.CharField(blank=True, max_length=128)),
                ('unit', models.CharField(blank=True, help_text='e.g., pcs, kg, liters', max_length=32)),
                ('min_stock_level', models.DecimalField(blank=True, decimal_places=2, help_text='Minimum stock level for alerts', max_digits=12, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('campus', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='orgsettings.campus')),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='StockMovement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('movement_type', models.CharField(choices=[('IN', 'Stock In'), ('OUT', 'Stock Out'), ('ADJUST', 'Adjustment')], default='IN', max_length=16)),
                ('quantity', models.DecimalField(decimal_places=2, max_digits=12)),
                ('reference', models.CharField(blank=True, help_text='PO number, invoice, etc.', max_length=128)),
                ('note', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='movements', to='core.inventoryitem')),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
        migrations.CreateModel(
            name='AssetAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=2, default=1, max_digits=12)),
                ('assigned_at', models.DateField(auto_now_add=True)),
                ('due_date', models.DateField(blank=True, null=True)),
                ('returned_at', models.DateField(blank=True, null=True)),
                ('status', models.CharField(choices=[('ACTIVE', 'Active'), ('RETURNED', 'Returned'), ('LOST', 'Lost'), ('DAMAGED', 'Damaged')], default='ACTIVE', max_length=16)),
                ('note', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('assigned_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_assignments', to=settings.AUTH_USER_MODEL)),
                ('assigned_to_student', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='asset_assignments', to='students.studentprofile')),
                ('assigned_to_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='asset_assignments', to=settings.AUTH_USER_MODEL)),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='core.inventoryitem')),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
        migrations.AddIndex(
            model_name='statushistory',
            index=models.Index(fields=['content_type', 'object_id'], name='core_status_content_9f0b8a_idx'),
        ),
        migrations.AddIndex(
            model_name='statushistory',
            index=models.Index(fields=['-created_at'], name='core_status_created_6e5c3e_idx'),
        ),
        migrations.AddIndex(
            model_name='actionlog',
            index=models.Index(fields=['content_type', 'object_id'], name='core_action_content_8a4d2f_idx'),
        ),
        migrations.AddIndex(
            model_name='actionlog',
            index=models.Index(fields=['-created_at'], name='core_action_created_1b9f4c_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['recipient', 'is_read'], name='core_notifi_recipie_7c3e1a_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['-created_at'], name='core_notifi_created_4d2a8b_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['audience', 'campus'], name='core_notifi_audienc_9e1f5c_idx'),
        ),
        migrations.AddIndex(
            model_name='stockmovement',
            index=models.Index(fields=['item', '-created_at'], name='core_stock_item_id_8f3c2d_idx'),
        ),
        migrations.AddIndex(
            model_name='assetassignment',
            index=models.Index(fields=['status', '-created_at'], name='core_asset_status_6d4e9a_idx'),
        ),
        migrations.AddConstraint(
            model_name='inventoryitem',
            constraint=models.UniqueConstraint(condition=models.Q(('sku', ''), _negated=True), fields=('sku',), name='unique_sku_when_not_blank'),
        ),
        migrations.AddConstraint(
            model_name='inventoryitem',
            constraint=models.UniqueConstraint(fields=('campus', 'name'), name='unique_item_per_campus'),
        ),
    ]
