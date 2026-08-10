from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("institutional", "0003_candidate_readiness_reviews"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="courseattempt",
            new_name="institution_course__8345e6_idx",
            old_name="institution_course__ee9fbc_idx",
        ),
        migrations.AlterField(
            model_name="academicattemptpolicy",
            name="dismissal_cgpa",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=5,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.AlterField(
            model_name="academicattemptpolicy",
            name="pass_grade_point",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("2.00"),
                max_digits=5,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.AlterField(
            model_name="academicattemptpolicy",
            name="probation_cgpa",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("2.00"),
                max_digits=5,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.AlterField(
            model_name="courseattempt",
            name="credits",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("1.00"),
                max_digits=6,
                validators=[django.core.validators.MinValueValidator(Decimal("0.01"))],
            ),
        ),
    ]
