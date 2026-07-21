from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("activities", "0002_phase8_co_curricular_consolidation"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="activitysession",
            old_name="activities__activit_2e4894_idx",
            new_name="activities__activit_a2b352_idx",
        ),
    ]
