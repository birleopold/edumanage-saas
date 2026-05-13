# Data migration: default templates include portal/receipt links

from django.db import migrations


def forwards(apps, schema_editor):
    CommunicationTemplate = apps.get_model("finance", "CommunicationTemplate")
    fee_body = (
        "Hello {{parent_name}}, this is {{school_name}}. "
        "Fee reminder for {{student_name}}: {{amount}} (invoice {{invoice_ref}}). "
        "{{due_line}} {{portal_url}} Thank you."
    )
    pay_body = (
        "{{school_name}} confirms payment of {{amount}} for {{student_name}}. Ref {{payment_ref}}. "
        "{{receipt_url}} Thank you, {{parent_name}}."
    )
    for code, body in (
        ("fee_reminder_default", fee_body),
        ("payment_receipt_default", pay_body),
    ):
        CommunicationTemplate.objects.filter(code=code).update(body=body)


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0007_communication_template"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
