from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import SubjectCombination, SubjectCombinationCourse
from .pathway_extensions import SubjectCombinationPolicy, SubjectRoleProfile


@receiver(post_save, sender=SubjectCombination)
def ensure_combination_policy(sender, instance, **kwargs):
    legacy_capacity = (instance.settings or {}).get("capacity")
    defaults = {}
    if legacy_capacity not in (None, ""):
        try:
            defaults["maximum_students"] = int(legacy_capacity)
        except (TypeError, ValueError):
            pass
    SubjectCombinationPolicy.objects.get_or_create(
        combination=instance,
        defaults=defaults,
    )


@receiver(post_save, sender=SubjectCombinationCourse)
def ensure_subject_role_profile(sender, instance, **kwargs):
    role = instance.role if instance.role in {
        SubjectRoleProfile.CORE,
        SubjectRoleProfile.ELECTIVE,
        SubjectRoleProfile.OPTIONAL,
    } else SubjectRoleProfile.CORE
    SubjectRoleProfile.objects.get_or_create(
        membership=instance,
        defaults={"academic_role": role},
    )
