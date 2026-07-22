from django.core.exceptions import ValidationError
from django.db import models


class SubjectCombinationPolicy(models.Model):
    combination = models.OneToOneField(
        "academics.SubjectCombination",
        on_delete=models.CASCADE,
        related_name="academic_policy",
    )
    maximum_students = models.PositiveIntegerField(null=True, blank=True)
    minimum_principal_subjects = models.PositiveSmallIntegerField(default=0)
    maximum_principal_subjects = models.PositiveSmallIntegerField(null=True, blank=True)
    minimum_subsidiary_subjects = models.PositiveSmallIntegerField(default=0)
    maximum_subsidiary_subjects = models.PositiveSmallIntegerField(null=True, blank=True)
    require_general_paper = models.BooleanField(default=False)
    settings = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("combination__pathway", "combination__name")

    def __str__(self):
        return f"Policy — {self.combination}"

    def clean(self):
        super().clean()
        errors = {}
        if self.maximum_students is not None and self.maximum_students < 1:
            errors["maximum_students"] = "Maximum students must be at least one."
        if (
            self.maximum_principal_subjects is not None
            and self.maximum_principal_subjects < self.minimum_principal_subjects
        ):
            errors["maximum_principal_subjects"] = (
                "Maximum principal subjects cannot be below the minimum."
            )
        if (
            self.maximum_subsidiary_subjects is not None
            and self.maximum_subsidiary_subjects < self.minimum_subsidiary_subjects
        ):
            errors["maximum_subsidiary_subjects"] = (
                "Maximum subsidiary subjects cannot be below the minimum."
            )
        if errors:
            raise ValidationError(errors)


class SubjectRoleProfile(models.Model):
    CORE = "CORE"
    ELECTIVE = "ELECTIVE"
    OPTIONAL = "OPTIONAL"
    PRINCIPAL = "PRINCIPAL"
    SUBSIDIARY = "SUBSIDIARY"
    COMPULSORY = "COMPULSORY"
    GENERAL_PAPER = "GENERAL_PAPER"
    SUBSIDIARY_ICT = "SUBSIDIARY_ICT"
    SUBSIDIARY_MATHEMATICS = "SUBSIDIARY_MATHEMATICS"

    ROLE_CHOICES = (
        (CORE, "Core subject"),
        (ELECTIVE, "Elective subject"),
        (OPTIONAL, "Optional subject"),
        (PRINCIPAL, "Principal subject"),
        (SUBSIDIARY, "Subsidiary subject"),
        (COMPULSORY, "Compulsory subject"),
        (GENERAL_PAPER, "General Paper"),
        (SUBSIDIARY_ICT, "Subsidiary ICT"),
        (SUBSIDIARY_MATHEMATICS, "Subsidiary Mathematics"),
    )

    membership = models.OneToOneField(
        "academics.SubjectCombinationCourse",
        on_delete=models.CASCADE,
        related_name="academic_role_profile",
    )
    academic_role = models.CharField(
        max_length=32,
        choices=ROLE_CHOICES,
        default=CORE,
    )
    contributes_principal_points = models.BooleanField(default=False)
    contributes_subsidiary_points = models.BooleanField(default=False)
    required_for_completion = models.BooleanField(default=False)
    settings = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = (
            "membership__combination",
            "membership__order",
            "membership__course__name",
        )

    def __str__(self):
        return f"{self.membership.course} — {self.get_academic_role_display()}"

    def clean(self):
        super().clean()
        errors = {}
        principal_role = self.academic_role == self.PRINCIPAL
        subsidiary_role = self.academic_role in {
            self.SUBSIDIARY,
            self.GENERAL_PAPER,
            self.SUBSIDIARY_ICT,
            self.SUBSIDIARY_MATHEMATICS,
        }
        if self.contributes_principal_points and not principal_role:
            errors["contributes_principal_points"] = (
                "Only a principal subject can contribute principal points."
            )
        if self.contributes_subsidiary_points and not subsidiary_role:
            errors["contributes_subsidiary_points"] = (
                "Only a subsidiary-type subject can contribute subsidiary points."
            )
        if self.contributes_principal_points and self.contributes_subsidiary_points:
            errors["contributes_subsidiary_points"] = (
                "A subject cannot contribute both principal and subsidiary points."
            )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.academic_role == self.PRINCIPAL:
            self.contributes_principal_points = True
            self.contributes_subsidiary_points = False
        elif self.academic_role in {
            self.SUBSIDIARY,
            self.GENERAL_PAPER,
            self.SUBSIDIARY_ICT,
            self.SUBSIDIARY_MATHEMATICS,
        }:
            self.contributes_principal_points = False
            self.contributes_subsidiary_points = True
        super().save(*args, **kwargs)
