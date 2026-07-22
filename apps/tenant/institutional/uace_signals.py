from django.core.exceptions import ValidationError
from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import LearnerSubjectCombination
from .uace_services import combination_structure_errors, registration_capacity_errors


@receiver(pre_save, sender=LearnerSubjectCombination)
def validate_registered_subject_combination(sender, instance, **kwargs):
    if not instance.is_active or not instance.combination_id:
        return
    structure_errors = combination_structure_errors(instance.combination)
    capacity_errors = registration_capacity_errors(instance)
    errors = structure_errors + capacity_errors
    if errors:
        raise ValidationError({"combination": errors})
