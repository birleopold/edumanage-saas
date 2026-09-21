import hashlib

from django.db import migrations, models


def hash_existing_tokens(apps, schema_editor):
    PasswordSetupToken = apps.get_model("users", "PasswordSetupToken")
    for setup_token in PasswordSetupToken.objects.only("pk", "token").iterator():
        setup_token.token = hashlib.sha256(setup_token.token.encode("utf-8")).hexdigest()
        setup_token.save(update_fields=["token"])


class Migration(migrations.Migration):
    dependencies = [("users", "0009_merge_20260624_1216")]

    operations = [
        migrations.RunPython(hash_existing_tokens, migrations.RunPython.noop),
        migrations.RenameField(
            model_name="passwordsetuptoken",
            old_name="token",
            new_name="token_digest",
        ),
        migrations.AlterField(
            model_name="passwordsetuptoken",
            name="token_digest",
            field=models.CharField(db_index=True, max_length=64, unique=True),
        ),
    ]
