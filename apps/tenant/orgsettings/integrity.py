from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable

from django.db.models import Count, F, Q
from django.db.models.functions import Lower, Trim

from apps.tenant.academics.models import ClassGroup, Course, CourseOffering, Enrollment, Stream
from apps.tenant.admissions.models import Applicant
from apps.tenant.finance.models import Invoice, MobilePaymentRequest, Payment
from apps.tenant.hr.models import StaffProfile
from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile
from apps.tenant.timetable.models import TimetableEntry
from apps.tenant.users.models import Role, User, UserRole


@dataclass(frozen=True)
class IntegrityIssue:
    severity: str
    code: str
    count: int
    message: str
    samples: tuple[str, ...] = ()


def _normalized(value) -> str:
    return str(value or "").strip().lower()


def _sample_groups(rows: Iterable[dict], fields: tuple[str, ...], limit: int = 5) -> tuple[str, ...]:
    samples = []
    for row in list(rows)[:limit]:
        values = ", ".join(f"{field}={row.get(field)!r}" for field in fields)
        samples.append(f"{values}, count={row.get('total', 0)}")
    return tuple(samples)


def _profile_identity_key(profile):
    if profile.user_id:
        return ("user", profile.user_id)
    campus_id = profile.campus_id or 0
    staff_id = _normalized(getattr(profile, "staff_id", ""))
    if staff_id:
        return ("staff_id", campus_id, staff_id)
    email = _normalized(getattr(profile, "email", ""))
    if email:
        return ("email", campus_id, email)
    return (
        "name",
        campus_id,
        _normalized(getattr(profile, "first_name", "")),
        _normalized(getattr(profile, "last_name", "")),
    )


def _add_duplicate_issue(
    issues: list[IntegrityIssue],
    *,
    queryset,
    normalized_field: str,
    code: str,
    message: str,
    severity: str = "ERROR",
    group_fields: tuple[str, ...] = (),
):
    annotation = {"normalized_value": Lower(Trim(normalized_field))}
    values = (*group_fields, "normalized_value")
    rows = list(
        queryset.exclude(**{normalized_field: ""})
        .annotate(**annotation)
        .values(*values)
        .annotate(total=Count("id"))
        .filter(total__gt=1)
        .order_by("-total")
    )
    if rows:
        issues.append(
            IntegrityIssue(
                severity=severity,
                code=code,
                count=len(rows),
                message=message,
                samples=_sample_groups(rows, values),
            )
        )


def audit_current_tenant() -> list[IntegrityIssue]:
    """Return read-only integrity findings for the active tenant schema."""

    issues: list[IntegrityIssue] = []

    # Account and role identity.
    _add_duplicate_issue(
        issues,
        queryset=User.objects.all(),
        normalized_field="email",
        code="DUPLICATE_USER_EMAIL",
        message="Multiple user accounts share the same non-empty email address.",
    )

    duplicate_roles = list(
        UserRole.objects.values("user_id", "role_id", "campus_id")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
        .order_by("-total")
    )
    if duplicate_roles:
        issues.append(
            IntegrityIssue(
                "ERROR",
                "DUPLICATE_USER_ROLE",
                len(duplicate_roles),
                "The same role is assigned repeatedly to a user in the same campus scope.",
                _sample_groups(duplicate_roles, ("user_id", "role_id", "campus_id")),
            )
        )

    role_users = {
        code: set(UserRole.objects.filter(role__code=code).values_list("user_id", flat=True))
        for code in (Role.STUDENT, Role.PARENT, Role.TEACHER)
    }

    # Students.
    for field, code, label in (
        ("student_id", "DUPLICATE_STUDENT_ID", "student number"),
        ("learner_id", "DUPLICATE_LEARNER_ID", "government/EMIS learner ID"),
        ("nin", "DUPLICATE_STUDENT_NIN", "student NIN"),
    ):
        _add_duplicate_issue(
            issues,
            queryset=StudentProfile.objects.all(),
            normalized_field=field,
            code=code,
            message=f"Multiple student records share the same non-empty {label}.",
        )

    no_campus = StudentProfile.objects.filter(is_active=True, campus__isnull=True).count()
    if no_campus:
        issues.append(IntegrityIssue("ERROR", "ACTIVE_STUDENT_WITHOUT_CAMPUS", no_campus, "Active students are not assigned to a campus."))

    student_role_missing = sum(
        1
        for user_id in StudentProfile.objects.exclude(user__isnull=True).values_list("user_id", flat=True)
        if user_id not in role_users[Role.STUDENT]
    )
    if student_role_missing:
        issues.append(IntegrityIssue("ERROR", "STUDENT_ROLE_MISSING", student_role_missing, "Linked student accounts do not have the Student role."))

    student_email_mismatches = []
    for student in StudentProfile.objects.select_related("user").exclude(user__isnull=True):
        if student.email and student.user.email and _normalized(student.email) != _normalized(student.user.email):
            student_email_mismatches.append(f"student={student.pk}, user={student.user_id}")
    if student_email_mismatches:
        issues.append(
            IntegrityIssue(
                "WARNING",
                "STUDENT_USER_EMAIL_MISMATCH",
                len(student_email_mismatches),
                "Student profile email differs from the linked login account email.",
                tuple(student_email_mismatches[:5]),
            )
        )

    stream_campus_mismatch = StudentProfile.objects.filter(
        campus__isnull=False,
        stream__class_group__campus__isnull=False,
    ).exclude(campus_id=F("stream__class_group__campus_id")).count()
    if stream_campus_mismatch:
        issues.append(IntegrityIssue("ERROR", "STUDENT_STREAM_CAMPUS_MISMATCH", stream_campus_mismatch, "Students are assigned to streams belonging to another campus."))

    # Parents and guardian links.
    _add_duplicate_issue(
        issues,
        queryset=ParentProfile.objects.all(),
        normalized_field="email",
        code="DUPLICATE_PARENT_EMAIL",
        message="Multiple parent profiles share the same non-empty email address; review before merging because shared family emails may be intentional.",
        severity="WARNING",
    )
    _add_duplicate_issue(
        issues,
        queryset=ParentProfile.objects.all(),
        normalized_field="phone",
        code="DUPLICATE_PARENT_PHONE",
        message="Multiple parent profiles share the same non-empty phone number; review before merging because shared family phones may be intentional.",
        severity="WARNING",
    )

    parent_role_missing = sum(
        1
        for user_id in ParentProfile.objects.exclude(user__isnull=True).values_list("user_id", flat=True)
        if user_id not in role_users[Role.PARENT]
    )
    if parent_role_missing:
        issues.append(IntegrityIssue("ERROR", "PARENT_ROLE_MISSING", parent_role_missing, "Linked parent accounts do not have the Parent role."))

    parent_email_mismatches = []
    for parent in ParentProfile.objects.select_related("user").exclude(user__isnull=True):
        if parent.email and parent.user.email and _normalized(parent.email) != _normalized(parent.user.email):
            parent_email_mismatches.append(f"parent={parent.pk}, user={parent.user_id}")
    if parent_email_mismatches:
        issues.append(
            IntegrityIssue(
                "WARNING",
                "PARENT_USER_EMAIL_MISMATCH",
                len(parent_email_mismatches),
                "Parent profile email differs from the linked login account email.",
                tuple(parent_email_mismatches[:5]),
            )
        )

    multiple_primary = list(
        ParentStudentLink.objects.filter(is_primary=True)
        .values("student_id")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
        .order_by("-total")
    )
    if multiple_primary:
        issues.append(
            IntegrityIssue(
                "ERROR",
                "MULTIPLE_PRIMARY_GUARDIANS",
                len(multiple_primary),
                "Students have more than one guardian marked as primary.",
                _sample_groups(multiple_primary, ("student_id",)),
            )
        )

    # Admissions conversion consistency.
    admitted_without_student = Applicant.objects.filter(status=Applicant.ADMITTED, created_student__isnull=True).count()
    if admitted_without_student:
        issues.append(IntegrityIssue("ERROR", "ADMITTED_WITHOUT_STUDENT", admitted_without_student, "Applicants are marked admitted but have no linked student record."))

    linked_not_admitted = Applicant.objects.exclude(created_student__isnull=True).exclude(status=Applicant.ADMITTED).count()
    if linked_not_admitted:
        issues.append(IntegrityIssue("ERROR", "STUDENT_LINKED_NOT_ADMITTED", linked_not_admitted, "Applicants have a linked student but are not marked admitted."))

    repeated_student_links = list(
        Applicant.objects.exclude(created_student__isnull=True)
        .values("created_student_id")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
        .order_by("-total")
    )
    if repeated_student_links:
        issues.append(
            IntegrityIssue(
                "ERROR",
                "MULTIPLE_APPLICANTS_ONE_STUDENT",
                len(repeated_student_links),
                "More than one applicant record points to the same student.",
                _sample_groups(repeated_student_links, ("created_student_id",)),
            )
        )

    # HR and academic teacher identity.
    for model, code, label in (
        (StaffProfile, "DUPLICATE_HR_STAFF_ID", "HR staff number"),
        (TeacherProfile, "DUPLICATE_TEACHER_STAFF_ID", "teacher staff number"),
    ):
        _add_duplicate_issue(
            issues,
            queryset=model.objects.all(),
            normalized_field="staff_id",
            code=code,
            message=f"Multiple records share the same non-empty {label}.",
        )

    staff_profiles = list(StaffProfile.objects.select_related("user", "campus"))
    teacher_profiles = list(TeacherProfile.objects.select_related("user", "campus"))
    staff_by_key = defaultdict(list)
    teachers_by_key = defaultdict(list)
    for staff in staff_profiles:
        staff_by_key[_profile_identity_key(staff)].append(staff)
    for teacher in teacher_profiles:
        teachers_by_key[_profile_identity_key(teacher)].append(teacher)

    duplicate_staff_identity = [key for key, records in staff_by_key.items() if len(records) > 1]
    duplicate_teacher_identity = [key for key, records in teachers_by_key.items() if len(records) > 1]
    if duplicate_staff_identity:
        issues.append(IntegrityIssue("ERROR", "DUPLICATE_HR_IDENTITY", len(duplicate_staff_identity), "HR contains repeated identity records after normalization.", tuple(map(str, duplicate_staff_identity[:5]))))
    if duplicate_teacher_identity:
        issues.append(IntegrityIssue("ERROR", "DUPLICATE_TEACHER_IDENTITY", len(duplicate_teacher_identity), "Teachers contains repeated identity records after normalization.", tuple(map(str, duplicate_teacher_identity[:5]))))

    teaching_staff_keys = {
        _profile_identity_key(staff)
        for staff in staff_profiles
        if staff.staff_category == StaffProfile.TEACHING or (staff.user_id and staff.user_id in role_users[Role.TEACHER])
    }
    active_teacher_keys = {_profile_identity_key(teacher) for teacher in teacher_profiles if teacher.is_active}
    missing_teacher = teaching_staff_keys - set(teachers_by_key)
    missing_staff = active_teacher_keys - set(staff_by_key)
    if missing_teacher:
        issues.append(IntegrityIssue("ERROR", "TEACHING_STAFF_WITHOUT_TEACHER", len(missing_teacher), "Teaching HR records have no matching teacher profile.", tuple(map(str, list(missing_teacher)[:5]))))
    if missing_staff:
        issues.append(IntegrityIssue("ERROR", "TEACHER_WITHOUT_HR_STAFF", len(missing_staff), "Active teacher profiles have no matching HR staff record.", tuple(map(str, list(missing_staff)[:5]))))

    teacher_role_missing = sum(
        1
        for teacher in teacher_profiles
        if teacher.user_id and teacher.user_id not in role_users[Role.TEACHER]
    )
    if teacher_role_missing:
        issues.append(IntegrityIssue("ERROR", "TEACHER_ROLE_MISSING", teacher_role_missing, "Linked teacher accounts do not have the Teacher role."))

    non_teaching_teacher_role = sum(
        1
        for staff in staff_profiles
        if staff.staff_category == StaffProfile.NON_TEACHING and staff.user_id in role_users[Role.TEACHER]
    )
    if non_teaching_teacher_role:
        issues.append(IntegrityIssue("WARNING", "NON_TEACHING_WITH_TEACHER_ROLE", non_teaching_teacher_role, "Non-teaching HR records are linked to accounts carrying the Teacher role."))

    mismatched_pairs = []
    for key in set(staff_by_key).intersection(teachers_by_key):
        if len(staff_by_key[key]) != 1 or len(teachers_by_key[key]) != 1:
            continue
        staff = staff_by_key[key][0]
        teacher = teachers_by_key[key][0]
        compared = (
            staff.user_id == teacher.user_id,
            staff.campus_id == teacher.campus_id,
            _normalized(staff.staff_id) == _normalized(teacher.staff_id),
            _normalized(staff.first_name) == _normalized(teacher.first_name),
            _normalized(staff.last_name) == _normalized(teacher.last_name),
            _normalized(staff.phone) == _normalized(teacher.phone),
            _normalized(staff.email) == _normalized(teacher.email),
            staff.is_active == teacher.is_active,
        )
        if not all(compared):
            mismatched_pairs.append(str(key))
    if mismatched_pairs:
        issues.append(IntegrityIssue("ERROR", "TEACHER_HR_DATA_MISMATCH", len(mismatched_pairs), "Matching teacher and HR records disagree on identity, campus, user, or active status.", tuple(mismatched_pairs[:5])))

    # Academic setup and enrollment.
    duplicate_class_groups = list(
        ClassGroup.objects.annotate(normalized_name=Lower(Trim("name")))
        .values("campus_id", "normalized_name")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
        .order_by("-total")
    )
    if duplicate_class_groups:
        issues.append(IntegrityIssue("ERROR", "DUPLICATE_CLASS_GROUP", len(duplicate_class_groups), "The same class/group name exists more than once in a campus.", _sample_groups(duplicate_class_groups, ("campus_id", "normalized_name"))))

    duplicate_courses = list(
        Course.objects.annotate(normalized_name=Lower(Trim("name")))
        .values("level_id", "program_id", "normalized_name")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
        .order_by("-total")
    )
    if duplicate_courses:
        issues.append(IntegrityIssue("WARNING", "DUPLICATE_COURSE", len(duplicate_courses), "Courses repeat within the same level/program scope.", _sample_groups(duplicate_courses, ("level_id", "program_id", "normalized_name"))))

    duplicate_offerings = list(
        CourseOffering.objects.values("campus_id", "course_id", "term_id", "class_group_id")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
        .order_by("-total")
    )
    if duplicate_offerings:
        issues.append(IntegrityIssue("ERROR", "DUPLICATE_COURSE_OFFERING", len(duplicate_offerings), "The same subject/course is offered repeatedly to the same class in the same term.", _sample_groups(duplicate_offerings, ("campus_id", "course_id", "term_id", "class_group_id"))))

    offering_class_mismatch = CourseOffering.objects.filter(campus__isnull=False, class_group__campus__isnull=False).exclude(campus_id=F("class_group__campus_id")).count()
    if offering_class_mismatch:
        issues.append(IntegrityIssue("ERROR", "OFFERING_CLASS_CAMPUS_MISMATCH", offering_class_mismatch, "Course offerings and their class groups belong to different campuses."))

    offering_teacher_mismatch = CourseOffering.objects.filter(campus__isnull=False, teacher__campus__isnull=False).exclude(campus_id=F("teacher__campus_id")).count()
    if offering_teacher_mismatch:
        issues.append(IntegrityIssue("ERROR", "OFFERING_TEACHER_CAMPUS_MISMATCH", offering_teacher_mismatch, "Course offerings and assigned teachers belong to different campuses."))

    enrollment_offering_mismatch = Enrollment.objects.filter(campus__isnull=False, offering__campus__isnull=False).exclude(campus_id=F("offering__campus_id")).count()
    enrollment_student_mismatch = Enrollment.objects.filter(campus__isnull=False, student__campus__isnull=False).exclude(campus_id=F("student__campus_id")).count()
    if enrollment_offering_mismatch:
        issues.append(IntegrityIssue("ERROR", "ENROLLMENT_OFFERING_CAMPUS_MISMATCH", enrollment_offering_mismatch, "Enrollment campus differs from the course offering campus."))
    if enrollment_student_mismatch:
        issues.append(IntegrityIssue("ERROR", "ENROLLMENT_STUDENT_CAMPUS_MISMATCH", enrollment_student_mismatch, "Enrollment campus differs from the student's campus."))

    over_capacity = list(
        Stream.objects.annotate(active_students=Count("students", filter=Q(students__is_active=True)))
        .filter(active_students__gt=F("capacity"))
        .values("id", "name", "capacity", "active_students")
        .order_by("-active_students")
    )
    if over_capacity:
        issues.append(IntegrityIssue("WARNING", "STREAM_OVER_CAPACITY", len(over_capacity), "Active student counts exceed configured stream capacity.", tuple(f"stream={row['id']} {row['name']!r}, capacity={row['capacity']}, active={row['active_students']}" for row in over_capacity[:5])))

    # Timetable collisions that are not protected by the current unique constraint.
    for code, message, fields, filters in (
        ("TEACHER_TIMETABLE_CLASH", "A teacher is scheduled for multiple classes in the same period.", ("offering__teacher_id", "weekday", "period_id"), {"offering__teacher__isnull": False}),
        ("ROOM_TIMETABLE_CLASH", "A room is scheduled for multiple classes in the same period.", ("room_id", "weekday", "period_id"), {"room__isnull": False}),
        ("CLASS_TIMETABLE_CLASH", "A class group has multiple lessons in the same period.", ("offering__class_group_id", "weekday", "period_id"), {"offering__class_group__isnull": False}),
    ):
        rows = list(
            TimetableEntry.objects.filter(is_active=True, **filters)
            .values(*fields)
            .annotate(total=Count("id"))
            .filter(total__gt=1)
            .order_by("-total")
        )
        if rows:
            issues.append(IntegrityIssue("ERROR", code, len(rows), message, _sample_groups(rows, fields)))

    # Finance references and payment integrity.
    _add_duplicate_issue(
        issues,
        queryset=Invoice.objects.all(),
        normalized_field="reference",
        code="DUPLICATE_INVOICE_REFERENCE",
        message="Multiple invoices share the same non-empty reference.",
        severity="WARNING",
    )

    duplicate_payment_refs = list(
        Payment.objects.exclude(reference="")
        .annotate(normalized_reference=Lower(Trim("reference")))
        .values("method", "normalized_reference")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
        .order_by("-total")
    )
    if duplicate_payment_refs:
        issues.append(IntegrityIssue("WARNING", "DUPLICATE_PAYMENT_REFERENCE", len(duplicate_payment_refs), "Payment references repeat within the same payment method; verify against receipts or provider statements.", _sample_groups(duplicate_payment_refs, ("method", "normalized_reference"))))

    nonpositive_payments = Payment.objects.filter(amount__lte=0).count()
    if nonpositive_payments:
        issues.append(IntegrityIssue("ERROR", "NONPOSITIVE_PAYMENT", nonpositive_payments, "Payments have zero or negative amounts."))

    successful_without_payment = MobilePaymentRequest.objects.filter(status=MobilePaymentRequest.SUCCESSFUL, created_payment__isnull=True).count()
    if successful_without_payment:
        issues.append(IntegrityIssue("ERROR", "SUCCESSFUL_MOBILE_REQUEST_WITHOUT_PAYMENT", successful_without_payment, "Successful mobile payment requests have no created payment record."))

    duplicate_provider_refs = list(
        MobilePaymentRequest.objects.exclude(provider_reference="")
        .annotate(normalized_reference=Lower(Trim("provider_reference")))
        .values("normalized_reference")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
        .order_by("-total")
    )
    if duplicate_provider_refs:
        issues.append(IntegrityIssue("ERROR", "DUPLICATE_MOBILE_PROVIDER_REFERENCE", len(duplicate_provider_refs), "Mobile payment provider references are repeated.", _sample_groups(duplicate_provider_refs, ("normalized_reference",))))

    return sorted(issues, key=lambda item: (0 if item.severity == "ERROR" else 1, item.code))


def summarize_issues(issues: Iterable[IntegrityIssue]) -> Counter:
    return Counter(issue.severity for issue in issues)
