import django.db.models.deletion
from django.db import migrations, models


def bootstrap_pathway_policies(apps, schema_editor):
    SubjectCombination = apps.get_model("academics", "SubjectCombination")
    SubjectCombinationPolicy = apps.get_model(
        "academics",
        "SubjectCombinationPolicy",
    )
    SubjectCombinationCourse = apps.get_model(
        "academics",
        "SubjectCombinationCourse",
    )
    SubjectRoleProfile = apps.get_model("academics", "SubjectRoleProfile")

    existing_combination_ids = set(
        SubjectCombinationPolicy.objects.values_list("combination_id", flat=True)
    )
    policies = []
    for combination in SubjectCombination.objects.iterator():
        if combination.pk in existing_combination_ids:
            continue
        capacity = (combination.settings or {}).get("capacity")
        try:
            capacity = int(capacity) if capacity not in (None, "") else None
        except (TypeError, ValueError):
            capacity = None
        policies.append(
            SubjectCombinationPolicy(
                combination_id=combination.pk,
                maximum_students=capacity,
            )
        )
    SubjectCombinationPolicy.objects.bulk_create(policies, batch_size=500)

    existing_membership_ids = set(
        SubjectRoleProfile.objects.values_list("membership_id", flat=True)
    )
    roles = []
    for membership in SubjectCombinationCourse.objects.iterator():
        if membership.pk in existing_membership_ids:
            continue
        academic_role = membership.role if membership.role in {
            "CORE",
            "ELECTIVE",
            "OPTIONAL",
        } else "CORE"
        roles.append(
            SubjectRoleProfile(
                membership_id=membership.pk,
                academic_role=academic_role,
            )
        )
    SubjectRoleProfile.objects.bulk_create(roles, batch_size=1000)


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0004_programme_pathways_subject_combinations"),
    ]

    operations = [
        migrations.CreateModel(
            name="SubjectCombinationPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("maximum_students", models.PositiveIntegerField(blank=True, null=True)),
                ("minimum_principal_subjects", models.PositiveSmallIntegerField(default=0)),
                ("maximum_principal_subjects", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("minimum_subsidiary_subjects", models.PositiveSmallIntegerField(default=0)),
                ("maximum_subsidiary_subjects", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("require_general_paper", models.BooleanField(default=False)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("combination", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="academic_policy", to="academics.subjectcombination")),
            ],
            options={"ordering": ("combination__pathway", "combination__name")},
        ),
        migrations.CreateModel(
            name="SubjectRoleProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("academic_role", models.CharField(choices=[("CORE", "Core subject"), ("ELECTIVE", "Elective subject"), ("OPTIONAL", "Optional subject"), ("PRINCIPAL", "Principal subject"), ("SUBSIDIARY", "Subsidiary subject"), ("COMPULSORY", "Compulsory subject"), ("GENERAL_PAPER", "General Paper"), ("SUBSIDIARY_ICT", "Subsidiary ICT"), ("SUBSIDIARY_MATHEMATICS", "Subsidiary Mathematics")], default="CORE", max_length=32)),
                ("contributes_principal_points", models.BooleanField(default=False)),
                ("contributes_subsidiary_points", models.BooleanField(default=False)),
                ("required_for_completion", models.BooleanField(default=False)),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("membership", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="academic_role_profile", to="academics.subjectcombinationcourse")),
            ],
            options={"ordering": ("membership__combination", "membership__order", "membership__course__name")},
        ),
        migrations.RunPython(bootstrap_pathway_policies, migrations.RunPython.noop),
    ]
