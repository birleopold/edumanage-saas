from django.db import migrations, models


def normalize_current_calendar(apps, schema_editor):
    AcademicYear = apps.get_model("academics", "AcademicYear")
    AcademicTerm = apps.get_model("academics", "AcademicTerm")

    current_year_ids = list(
        AcademicYear.objects.filter(is_current=True)
        .order_by("-name", "-pk")
        .values_list("pk", flat=True)
    )
    if len(current_year_ids) > 1:
        AcademicYear.objects.filter(pk__in=current_year_ids[1:]).update(is_current=False)

    current_term_ids = list(
        AcademicTerm.objects.filter(is_current=True)
        .order_by("-year__name", "order", "-pk")
        .values_list("pk", flat=True)
    )
    if len(current_term_ids) > 1:
        AcademicTerm.objects.filter(pk__in=current_term_ids[1:]).update(is_current=False)


class Migration(migrations.Migration):
    dependencies = [("academics", "0005_subject_role_policies")]
    operations = [
        migrations.RunPython(normalize_current_calendar, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="academicyear",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_current", True)),
                fields=("is_current",),
                name="academics_one_current_year",
            ),
        ),
        migrations.AddConstraint(
            model_name="academicterm",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_current", True)),
                fields=("is_current",),
                name="academics_one_current_term",
            ),
        ),
    ]
