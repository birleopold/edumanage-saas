from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction

from apps.tenant.parents.models import ParentProfile, ParentStudentLink
from apps.tenant.students.models import StudentProfile
from apps.tenant.students.services import generate_next_student_id
from apps.tenant.users.models import Role

from .models import Applicant

User = get_user_model()


@dataclass(frozen=True)
class AdmissionPipelineSummary:
    total: int
    new: int
    in_review: int
    admitted: int
    rejected: int
    converted: int
    pending_conversion: int


@dataclass(frozen=True)
class ConversionResult:
    student: StudentProfile
    user: Optional[User]
    parent: Optional[ParentProfile]
    temporary_password: str | None
    credentials_sent: bool


def pipeline_summary(applicants) -> AdmissionPipelineSummary:
    applicants_list = list(applicants)
    return AdmissionPipelineSummary(
        total=len(applicants_list),
        new=sum(1 for applicant in applicants_list if applicant.status == Applicant.NEW),
        in_review=sum(1 for applicant in applicants_list if applicant.status == Applicant.IN_REVIEW),
        admitted=sum(1 for applicant in applicants_list if applicant.status == Applicant.ADMITTED),
        rejected=sum(1 for applicant in applicants_list if applicant.status == Applicant.REJECTED),
        converted=sum(1 for applicant in applicants_list if applicant.created_student_id),
        pending_conversion=sum(
            1 for applicant in applicants_list if applicant.status == Applicant.ADMITTED and not applicant.created_student_id
        ),
    )


def ensure_student_role():
    return Role.objects.get_or_create(code=Role.STUDENT, defaults={"name": "Student"})[0]


def ensure_parent_role():
    return Role.objects.get_or_create(code=Role.PARENT, defaults={"name": "Parent"})[0]


def _unique_username(base: str) -> str:
    base = (base or "user").strip().lower().replace(" ", "") or "user"
    username = base
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{counter}"
        counter += 1
    return username


def create_student_user(*, applicant: Applicant, student_id: str) -> tuple[User | None, str | None]:
    if not applicant.email:
        return None, None
    username = _unique_username(student_id or applicant.email.split("@")[0])
    temporary_password = User.objects.make_random_password(length=12)
    user = User.objects.create(username=username, email=applicant.email)
    user.set_password(temporary_password)
    if hasattr(user, "must_change_password"):
        user.must_change_password = True
        user.save(update_fields=["password", "must_change_password"])
    else:
        user.save(update_fields=["password"])
    user.roles.add(ensure_student_role())
    return user, temporary_password


def _split_guardian_name(name: str) -> tuple[str, str]:
    parts = (name or "").strip().split()
    if not parts:
        return "Guardian", ""
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]), parts[-1]


def get_or_create_guardian_parent(applicant: Applicant) -> ParentProfile | None:
    if not applicant.guardian_name and not applicant.phone and not applicant.email:
        return None

    parent = None
    if applicant.phone:
        parent = ParentProfile.objects.filter(phone=applicant.phone).first()
    if parent is None and applicant.email:
        parent = ParentProfile.objects.filter(email__iexact=applicant.email).first()

    if parent:
        changed = []
        if applicant.email and not parent.email:
            parent.email = applicant.email
            changed.append("email")
        if applicant.phone and not parent.phone:
            parent.phone = applicant.phone
            changed.append("phone")
        if changed:
            parent.save(update_fields=changed)
        return parent

    first_name, last_name = _split_guardian_name(applicant.guardian_name)
    return ParentProfile.objects.create(
        first_name=first_name,
        last_name=last_name,
        phone=applicant.phone or "",
        email=applicant.email or "",
        is_active=True,
    )


def send_student_credentials_email(*, applicant: Applicant, student: StudentProfile, temporary_password: str | None) -> bool:
    if not applicant.email or not temporary_password or not student.user_id:
        return False
    send_mail(
        subject="Your Student Portal Login",
        message=(
            f"Hello {student.first_name},\n\n"
            f"Your student number: {student.student_id}\n"
            f"Username: {student.user.username}\n"
            f"Temporary password: {temporary_password}\n\n"
            "Please change your password immediately after your first login."
        ),
        from_email=None,
        recipient_list=[applicant.email],
        fail_silently=True,
    )
    return True


@transaction.atomic
def convert_applicant_to_student(
    *,
    applicant: Applicant,
    campus,
    stream=None,
    student_id: str | None = None,
    create_student_login: bool = True,
    create_parent_link: bool = True,
    send_credentials_email_flag: bool = True,
) -> ConversionResult:
    if applicant.created_student_id:
        return ConversionResult(
            student=applicant.created_student,
            user=applicant.created_student.user,
            parent=None,
            temporary_password=None,
            credentials_sent=False,
        )

    if campus is None:
        raise ValueError("Campus is required before an applicant can be converted to a student.")

    final_student_id = (student_id or "").strip() or generate_next_student_id(campus)
    if StudentProfile.objects.filter(student_id__iexact=final_student_id).exists():
        raise ValueError("This student number is already in use.")

    user = None
    temporary_password = None
    if create_student_login:
        user, temporary_password = create_student_user(applicant=applicant, student_id=final_student_id)

    student = StudentProfile.objects.create(
        user=user,
        campus=campus,
        stream=stream,
        first_name=applicant.first_name,
        last_name=applicant.last_name,
        date_of_birth=applicant.date_of_birth,
        student_id=final_student_id,
        email=applicant.email or "",
        is_active=True,
    )

    parent = None
    if create_parent_link:
        parent = get_or_create_guardian_parent(applicant)
        if parent:
            ParentStudentLink.objects.update_or_create(
                parent=parent,
                student=student,
                defaults={
                    "relationship": applicant.guardian_relationship or "Guardian",
                    "is_primary": True,
                },
            )

    applicant.status = Applicant.ADMITTED
    applicant.created_student = student
    applicant.save(update_fields=["status", "created_student", "updated_at"])

    credentials_sent = False
    if send_credentials_email_flag:
        credentials_sent = send_student_credentials_email(
            applicant=applicant,
            student=student,
            temporary_password=temporary_password,
        )

    return ConversionResult(
        student=student,
        user=user,
        parent=parent,
        temporary_password=temporary_password,
        credentials_sent=credentials_sent,
    )
