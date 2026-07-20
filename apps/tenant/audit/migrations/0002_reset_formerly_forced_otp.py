from django.db import migrations


def reset_formerly_forced_otp(apps, schema_editor):
    """Return existing administrators to the new opt-in OTP default.

    Earlier production policy forced every administrator through email OTP and
    the verification view persisted is_enabled=True. Under the new policy,
    schools choose this protection explicitly from the account settings page.
    """
    UserTwoFactorSetting = apps.get_model("audit", "UserTwoFactorSetting")
    UserTwoFactorSetting.objects.filter(is_enabled=True).update(is_enabled=False)


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(reset_formerly_forced_otp, migrations.RunPython.noop),
    ]
