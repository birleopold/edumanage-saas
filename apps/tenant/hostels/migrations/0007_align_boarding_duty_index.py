from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("hostels", "0006_merge_guardian_contact_and_school_houses"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="boardingdutyroster",
            old_name="hostels_boa_status_1e8424_idx",
            new_name="hostels_boa_status_023ba6_idx",
        ),
    ]
