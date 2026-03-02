# Generated migration for campus admin role and campus-scoped permissions

from django.db import migrations, models
import django.db.models.deletion


def create_campus_admin_role(apps, schema_editor):
    """Create the CAMPUS_ADMIN role if it doesn't exist."""
    Role = apps.get_model('users', 'Role')
    Role.objects.get_or_create(
        code='CAMPUS_ADMIN',
        defaults={'name': 'Campus Admin'}
    )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
        ('orgsettings', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='role',
            name='code',
            field=models.CharField(
                choices=[
                    ('ADMIN', 'Admin'),
                    ('CAMPUS_ADMIN', 'Campus Admin'),
                    ('TEACHER', 'Teacher'),
                    ('STUDENT', 'Student'),
                    ('PARENT', 'Parent')
                ],
                max_length=32,
                unique=True
            ),
        ),
        migrations.AddField(
            model_name='userrole',
            name='campus',
            field=models.ForeignKey(
                blank=True,
                help_text='Campus scope for campus admin role',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='orgsettings.campus'
            ),
        ),
        migrations.AlterUniqueTogether(
            name='userrole',
            unique_together={('user', 'role', 'campus')},
        ),
        migrations.RunPython(create_campus_admin_role, migrations.RunPython.noop),
    ]
