from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.tenant.assessments.models import AssessmentType

from .models import ExamPaper, ExamScore
from .policy_models import ExamPaperPolicy, ExamScorePolicy


@receiver(post_save, sender=ExamPaper)
def ensure_exam_paper_policy(sender, instance, **kwargs):
    grading_mode = ExamPaperPolicy.NUMERIC
    if (
        instance.assessment_type_id
        and instance.assessment_type.kind == AssessmentType.COMPETENCY
    ):
        grading_mode = ExamPaperPolicy.COMPETENCY
    defaults = {
        "grading_mode": grading_mode,
        "show_on_report": instance.report_cards_enabled,
        "responsible_teacher_id": instance.offering.teacher_id,
    }
    policy, created = ExamPaperPolicy.objects.get_or_create(
        paper=instance,
        defaults=defaults,
    )
    update_fields = []
    if not created:
        if policy.show_on_report != instance.report_cards_enabled:
            policy.show_on_report = instance.report_cards_enabled
            update_fields.append("show_on_report")
        if not policy.responsible_teacher_id and instance.offering.teacher_id:
            policy.responsible_teacher_id = instance.offering.teacher_id
            update_fields.append("responsible_teacher")
        if update_fields:
            update_fields.append("updated_at")
            policy.save(update_fields=update_fields)


@receiver(post_save, sender=ExamScore)
def ensure_exam_score_policy(sender, instance, **kwargs):
    ExamScorePolicy.objects.get_or_create(score_record=instance)
