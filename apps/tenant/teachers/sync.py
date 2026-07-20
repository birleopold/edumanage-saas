from django.db import transaction
from django.db.models import Q

from apps.tenant.hr.models import StaffProfile
from apps.tenant.users.models import Role

from .models import TeacherProfile


IDENTITY_FIELDS = (
    "campus",
    "staff_id",
    "first_name",
    "last_name",
    "phone",
    "email",
    "is_active",
)


def _copy_identity(source, target) -> None:
    for field in IDENTITY_FIELDS:
        setattr(target, field, getattr(source, field))


def _teacher_role():
    role, _ = Role.objects.get_or_create(code=Role.TEACHER, defaults={"name": "Teacher"})
    return role


def _teacher_for_staff(staff: StaffProfile):
    if staff.user_id:
        teacher = TeacherProfile.objects.filter(user_id=staff.user_id).first()
        if teacher is not None:
            return teacher

    candidates = TeacherProfile.objects.filter(campus_id=staff.campus_id)
    if staff.user_id:
        candidates = candidates.filter(Q(user__isnull=True) | Q(user_id=staff.user_id))
    else:
        candidates = candidates.filter(user__isnull=True)

    if staff.staff_id:
        teacher = candidates.filter(staff_id__iexact=staff.staff_id).first()
        if teacher is not None:
            return teacher
    if staff.email:
        return candidates.filter(email__iexact=staff.email).first()
    return None


def _staff_for_teacher(teacher: TeacherProfile):
    if teacher.user_id:
        staff = StaffProfile.objects.filter(user_id=teacher.user_id).first()
        if staff is not None:
            return staff

    candidates = StaffProfile.objects.filter(campus_id=teacher.campus_id)
    if teacher.user_id:
        candidates = candidates.filter(Q(user__isnull=True) | Q(user_id=teacher.user_id))
    else:
        candidates = candidates.filter(user__isnull=True)

    if teacher.staff_id:
        staff = candidates.filter(staff_id__iexact=teacher.staff_id).first()
        if staff is not None:
            return staff
    if teacher.email:
        return candidates.filter(email__iexact=teacher.email).first()
    return None


@transaction.atomic
def ensure_teacher_for_staff(staff: StaffProfile, *, selected_role_code: str = ""):
    """Create or update the academic teacher profile for an HR staff member.

    StaffProfile remains the employment record. TeacherProfile is the academic
    extension used by classes, assessments, timetables, and teacher portals.
    Both profiles share one user account whenever an account exists.
    """

    has_teacher_role = bool(staff.user_id and staff.user.has_role(Role.TEACHER))
    should_be_teacher = (
        selected_role_code == Role.TEACHER
        or staff.staff_category == StaffProfile.TEACHING
        or has_teacher_role
    )

    teacher = _teacher_for_staff(staff)
    if not should_be_teacher:
        if teacher is not None and teacher.is_active:
            teacher.is_active = False
            teacher.save(update_fields=["is_active"])
        return None

    if staff.user_id:
        staff.user.roles.add(_teacher_role())

    if teacher is None:
        teacher = TeacherProfile()

    _copy_identity(staff, teacher)
    if staff.user_id and (teacher.user_id is None or teacher.user_id == staff.user_id):
        teacher.user = staff.user
    teacher.save()
    return teacher


@transaction.atomic
def ensure_staff_for_teacher(teacher: TeacherProfile):
    """Create or update the HR employment record for a teacher profile."""

    if teacher.user_id:
        teacher.user.roles.add(_teacher_role())

    staff = _staff_for_teacher(teacher)
    if staff is None:
        staff = StaffProfile(staff_category=StaffProfile.TEACHING)

    _copy_identity(teacher, staff)
    staff.staff_category = StaffProfile.TEACHING
    if teacher.user_id and (staff.user_id is None or staff.user_id == teacher.user_id):
        staff.user = teacher.user
    staff.save()
    return staff
