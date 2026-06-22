from django.db.models import Q
from django.utils import timezone

from apps.tenant.orgsettings.services import get_current_campus
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.users.models import Role

from .models import Poll


def role_audiences(user):
    values = [Poll.ALL]
    if user.has_role(Role.ADMIN) or user.has_role(Role.CAMPUS_ADMIN) or user.has_role(Role.PRINCIPAL):
        values.extend([Poll.ADMIN, Poll.STAFF])
    if user.has_role(Role.TEACHER):
        values.extend([Poll.TEACHERS, Poll.STAFF])
    if user.has_role(Role.STUDENT):
        values.append(Poll.STUDENTS)
    if user.has_role(Role.PARENT):
        values.append(Poll.PARENTS)
    return list(dict.fromkeys(values))


def profile_campus(request):
    user = request.user
    student = StudentProfile.objects.filter(user=user).select_related("campus").first()
    if student and student.campus:
        return student.campus
    teacher = TeacherProfile.objects.filter(user=user).select_related("campus").first()
    if teacher and teacher.campus:
        return teacher.campus
    return get_current_campus(request)


def polls_for_user(request, include_closed=False):
    user = request.user
    if not user.is_authenticated:
        return Poll.objects.none()
    now = timezone.now()
    qs = Poll.objects.prefetch_related("options", "specific_students", "specific_teachers").filter(is_active=True)
    if not include_closed:
        qs = qs.filter(Q(available_from__isnull=True) | Q(available_from__lte=now)).filter(Q(available_until__isnull=True) | Q(available_until__gte=now))
    campus = profile_campus(request)
    if campus:
        qs = qs.filter(Q(campus__isnull=True) | Q(campus=campus))
    else:
        qs = qs.filter(campus__isnull=True)
    qs = qs.filter(audience__in=role_audiences(user))
    student = StudentProfile.objects.filter(user=user).first()
    teacher = TeacherProfile.objects.filter(user=user).first()
    if student:
        qs = qs.filter(Q(specific_students__isnull=True) | Q(specific_students=student))
    elif teacher:
        qs = qs.filter(Q(specific_teachers__isnull=True) | Q(specific_teachers=teacher))
    else:
        qs = qs.filter(specific_students__isnull=True, specific_teachers__isnull=True)
    return qs.distinct().order_by("-created_at")


def request_key(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def current_vote(poll, request):
    if poll.is_anonymous:
        return poll.votes.filter(user__isnull=True, ip_address=request_key(request)).order_by("-voted_at").first()
    return poll.votes.filter(user=request.user).order_by("-voted_at").first()


def results_allowed(poll, request):
    return poll.show_results_before_voting or bool(current_vote(poll, request))
