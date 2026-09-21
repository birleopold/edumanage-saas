from django.db.models import Q

from apps.tenant.users.models import Role, UserRole

from .models import Announcement


ROLE_AUDIENCES = {
    Role.TEACHER: Announcement.TEACHERS,
    Role.STUDENT: Announcement.STUDENTS,
    Role.PARENT: Announcement.PARENTS,
}


def announcement_audiences_for_user(user):
    role_codes = set(user.roles.values_list("code", flat=True))
    return {ROLE_AUDIENCES[code] for code in role_codes if code in ROLE_AUDIENCES}


def announcement_campus_ids_for_user(user):
    role_codes = set(user.roles.values_list("code", flat=True))
    if getattr(user, "is_superuser", False) or role_codes.intersection({Role.ADMIN, Role.PRINCIPAL}):
        return None

    campus_ids = set()
    if Role.CAMPUS_ADMIN in role_codes:
        campus_ids.update(
            UserRole.objects.filter(
                user=user,
                role__code=Role.CAMPUS_ADMIN,
                campus__isnull=False,
            ).values_list("campus_id", flat=True)
        )
    teacher = getattr(user, "teacher_profile", None)
    if teacher and teacher.campus_id:
        campus_ids.add(teacher.campus_id)
    student = getattr(user, "student_profile", None)
    if student and student.campus_id:
        campus_ids.add(student.campus_id)
    parent = getattr(user, "parent_profile", None)
    if parent:
        from apps.tenant.parents.models import ParentStudentLink

        campus_ids.update(
            ParentStudentLink.objects.filter(
                parent=parent, student__campus__isnull=False
            ).values_list(
                "student__campus_id", flat=True
            )
        )
    return campus_ids


def visible_announcements_for_user(user, *, audiences=None, campus_id=None):
    allowed_audiences = set(audiences or announcement_audiences_for_user(user))
    audience_filter = Q(audience=Announcement.ALL)
    if allowed_audiences:
        audience_filter |= Q(audience__in=allowed_audiences)

    qs = Announcement.objects.filter(is_active=True).filter(audience_filter)
    campus_ids = announcement_campus_ids_for_user(user)
    if campus_ids is None:
        return qs
    if campus_id is not None:
        try:
            selected = int(campus_id)
        except (TypeError, ValueError):
            return qs.none()
        if selected not in campus_ids:
            return qs.none()
        campus_ids = {selected}
    return qs.filter(Q(campus__isnull=True) | Q(campus_id__in=campus_ids))
