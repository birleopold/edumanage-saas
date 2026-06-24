from django.db import migrations


def normalize_feature_flag_codes(apps, schema_editor):
    FeatureFlag = apps.get_model("orgsettings", "FeatureFlag")
    seen = {}
    for flag in FeatureFlag.objects.order_by("id"):
        normalized = (flag.code or "").strip().upper()
        if not normalized:
            continue
        key = (flag.campus_id, normalized)
        existing_id = seen.get(key)
        if existing_id is None:
            if flag.code != normalized:
                flag.code = normalized
                flag.save(update_fields=["code", "updated_at"])
            seen[key] = flag.id
            continue

        existing = FeatureFlag.objects.filter(pk=existing_id).first()
        if existing:
            existing.is_enabled = flag.is_enabled
            existing.save(update_fields=["is_enabled", "updated_at"])
        flag.delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("orgsettings", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(normalize_feature_flag_codes, noop_reverse),
    ]
