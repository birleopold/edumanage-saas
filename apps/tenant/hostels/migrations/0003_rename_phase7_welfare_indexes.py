from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("hostels", "0002_boarding_welfare_consolidation"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="boardingleave",
            new_name="hostels_boa_student_c6a894_idx",
            old_name="hostels_boa_student_18a627_idx",
        ),
        migrations.RenameIndex(
            model_name="boardingleave",
            new_name="hostels_boa_status_25068f_idx",
            old_name="hostels_boa_status_da9b47_idx",
        ),
        migrations.RenameIndex(
            model_name="welfarecase",
            new_name="hostels_wel_student_718c10_idx",
            old_name="hostels_wel_student_4d92e9_idx",
        ),
        migrations.RenameIndex(
            model_name="welfarecase",
            new_name="hostels_wel_campus__0a97ad_idx",
            old_name="hostels_wel_campus__07bcf1_idx",
        ),
    ]
