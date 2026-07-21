from __future__ import annotations

import csv
import io
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.tenant.students.models import StudentProfile

from .external_models import (
    ExternalCandidate,
    ExternalCandidateSubject,
    ExternalExamBoard,
    ExternalExamCentre,
    ExternalExamResult,
    ExternalExamSession,
    ExternalExamSubject,
    ExternalResultImportBatch,
)


def _deduplicate(messages):
    return list(dict.fromkeys(str(message) for message in messages if message))


def board_errors(board: ExternalExamBoard) -> list[str]:
    errors = []
    try:
        board.full_clean()
    except ValidationError as exc:
        errors.extend(exc.messages)
    return _deduplicate(errors)


def centre_errors(centre: ExternalExamCentre) -> list[str]:
    errors = []
    try:
        centre.full_clean()
    except ValidationError as exc:
        errors.extend(exc.messages)
    return _deduplicate(errors)


def session_errors(session: ExternalExamSession) -> list[str]:
    errors = []
    try:
        session.full_clean()
    except ValidationError as exc:
        errors.extend(exc.messages)
    if session.is_active and not session.subjects.filter(is_active=True).exists():
        errors.append("The external examination session has no active subjects.")
    return _deduplicate(errors)


def subject_errors(subject: ExternalExamSubject) -> list[str]:
    errors = []
    try:
        subject.full_clean()
    except ValidationError as exc:
        errors.extend(exc.messages)
    return _deduplicate(errors)


def candidate_errors(candidate: ExternalCandidate) -> list[str]:
    errors = []
    try:
        candidate.full_clean()
    except ValidationError as exc:
        errors.extend(exc.messages)
    if candidate.is_active and not candidate.subject_registrations.exclude(
        status=ExternalCandidateSubject.WITHDRAWN
    ).exists():
        errors.append("The candidate has no active subject registrations.")
    return _deduplicate(errors)


def _student_stage(student):
    if not student.stream_id or not student.stream.class_group.level_id:
        return None
    try:
        from apps.tenant.education_frameworks.models import InstitutionEducationProfile
        from apps.tenant.education_frameworks.services import resolve_level_stage

        profile = InstitutionEducationProfile.objects.filter(is_active=True).first()
        if not profile:
            return None
        return resolve_level_stage(student.stream.class_group.level, profile)
    except Exception:
        return None


def student_matches_session(student: StudentProfile, session: ExternalExamSession) -> bool:
    if not student.is_active:
        return False
    if session.campus_id and student.campus_id != session.campus_id:
        return False
    class_group = student.stream.class_group if student.stream_id else None
    if session.level_id and (not class_group or class_group.level_id != session.level_id):
        return False
    if session.program_id and (not class_group or class_group.program_id != session.program_id):
        return False
    if session.stage_id:
        stage = _student_stage(student)
        if not stage or stage.pk != session.stage_id:
            return False
    return True


def eligible_students(session: ExternalExamSession):
    queryset = StudentProfile.objects.filter(is_active=True).select_related(
        "campus",
        "stream",
        "stream__class_group",
        "stream__class_group__level",
        "stream__class_group__program",
    )
    if session.campus_id:
        queryset = queryset.filter(campus_id=session.campus_id)
    if session.level_id:
        queryset = queryset.filter(stream__class_group__level_id=session.level_id)
    if session.program_id:
        queryset = queryset.filter(stream__class_group__program_id=session.program_id)
    students = list(queryset.order_by("last_name", "first_name", "pk"))
    if session.stage_id:
        students = [student for student in students if student_matches_session(student, session)]
    return students


def candidate_number_for(session: ExternalExamSession, sequence: int) -> str:
    prefix = (session.candidate_prefix or f"{session.code}-").strip().upper()
    return f"{prefix}{sequence:0{session.candidate_number_padding}d}"


def candidate_registration_preview(session: ExternalExamSession) -> dict:
    students = eligible_students(session)
    existing_ids = set(session.candidates.values_list("student_id", flat=True))
    missing = [student for student in students if student.pk not in existing_ids]
    return {
        "eligible_count": len(students),
        "existing_count": len(students) - len(missing),
        "missing_count": len(missing),
        "missing_students": missing,
    }


def register_eligible_candidates(session: ExternalExamSession, *, dry_run=False) -> dict:
    if not session.registration_is_open:
        raise ValidationError("Candidate registration is not currently open for this session.")
    preview = candidate_registration_preview(session)
    summary = {
        "eligible_count": preview["eligible_count"],
        "existing_count": preview["existing_count"],
        "created_count": preview["missing_count"],
        "dry_run": bool(dry_run),
    }
    if dry_run or not preview["missing_students"]:
        return summary

    with transaction.atomic():
        locked = ExternalExamSession.objects.select_for_update().get(pk=session.pk)
        sequence = locked.next_candidate_sequence
        for student in preview["missing_students"]:
            while ExternalCandidate.objects.filter(
                session=locked,
                candidate_number=candidate_number_for(locked, sequence),
            ).exists():
                sequence += 1
            ExternalCandidate.objects.create(
                session=locked,
                student=student,
                centre=locked.centre,
                candidate_number=candidate_number_for(locked, sequence),
                status=ExternalCandidate.REGISTERED,
            )
            sequence += 1
        locked.next_candidate_sequence = sequence
        locked.save(update_fields=["next_candidate_sequence", "updated_at"])
    return summary


def compulsory_subject_preview(session: ExternalExamSession, candidate=None) -> dict:
    subjects = list(session.subjects.filter(is_active=True, is_compulsory=True).order_by("order", "pk"))
    candidates = session.candidates.filter(is_active=True).exclude(status=ExternalCandidate.WITHDRAWN)
    if candidate is not None:
        candidates = candidates.filter(pk=candidate.pk)
    candidates = list(candidates.order_by("candidate_number"))
    existing = set(
        ExternalCandidateSubject.objects.filter(candidate__in=candidates, subject__in=subjects).values_list(
            "candidate_id", "subject_id"
        )
    )
    missing = [
        (candidate_item, subject)
        for candidate_item in candidates
        for subject in subjects
        if (candidate_item.pk, subject.pk) not in existing
    ]
    return {
        "candidate_count": len(candidates),
        "subject_count": len(subjects),
        "existing_count": len(candidates) * len(subjects) - len(missing),
        "missing_count": len(missing),
        "missing": missing,
    }


def register_compulsory_subjects(session: ExternalExamSession, *, candidate=None, dry_run=False) -> dict:
    preview = compulsory_subject_preview(session, candidate=candidate)
    if not dry_run:
        ExternalCandidateSubject.objects.bulk_create(
            [
                ExternalCandidateSubject(candidate=candidate_item, subject=subject)
                for candidate_item, subject in preview["missing"]
            ],
            ignore_conflicts=True,
        )
    return {
        "candidate_count": preview["candidate_count"],
        "subject_count": preview["subject_count"],
        "existing_count": preview["existing_count"],
        "created_count": preview["missing_count"],
        "dry_run": bool(dry_run),
    }


def external_exam_readiness() -> dict:
    boards = list(ExternalExamBoard.objects.all())
    centres = list(ExternalExamCentre.objects.select_related("board", "campus"))
    sessions = list(
        ExternalExamSession.objects.select_related(
            "board", "centre", "academic_year", "campus", "stage", "level", "program", "linked_exam"
        ).prefetch_related("subjects")
    )
    candidates = list(
        ExternalCandidate.objects.select_related("session", "student", "centre").prefetch_related(
            "subject_registrations"
        )
    )
    invalid_boards = [{"object": item, "errors": board_errors(item)} for item in boards]
    invalid_centres = [{"object": item, "errors": centre_errors(item)} for item in centres]
    invalid_sessions = [{"object": item, "errors": session_errors(item)} for item in sessions]
    invalid_candidates = [{"object": item, "errors": candidate_errors(item)} for item in candidates]
    invalid_boards = [row for row in invalid_boards if row["errors"]]
    invalid_centres = [row for row in invalid_centres if row["errors"]]
    invalid_sessions = [row for row in invalid_sessions if row["errors"]]
    invalid_candidates = [row for row in invalid_candidates if row["errors"]]
    checks = {
        "active_board_available": ExternalExamBoard.objects.filter(is_active=True).exists(),
        "boards_valid": not invalid_boards,
        "centres_valid": not invalid_centres,
        "sessions_valid": not invalid_sessions,
        "candidates_valid": not invalid_candidates,
    }
    return {
        "ready": all(checks.values()),
        "checks": checks,
        "board_count": len(boards),
        "centre_count": len(centres),
        "session_count": len(sessions),
        "candidate_count": len(candidates),
        "subject_count": ExternalExamSubject.objects.count(),
        "result_count": ExternalExamResult.objects.count(),
        "invalid_boards": invalid_boards,
        "invalid_centres": invalid_centres,
        "invalid_sessions": invalid_sessions,
        "invalid_candidates": invalid_candidates,
        "invalid_count": sum(
            len(rows)
            for rows in (invalid_boards, invalid_centres, invalid_sessions, invalid_candidates)
        ),
    }


def candidate_export_rows(session: ExternalExamSession):
    candidates = session.candidates.select_related("student", "centre").prefetch_related(
        "subject_registrations__subject__course"
    ).order_by("candidate_number")
    for candidate in candidates:
        subjects = candidate.subject_registrations.exclude(
            status=ExternalCandidateSubject.WITHDRAWN
        ).select_related("subject__course").order_by("subject__order", "subject__subject_code")
        subject_codes = ";".join(item.subject.subject_code for item in subjects)
        yield {
            "candidate_number": candidate.candidate_number,
            "student_id": candidate.student.student_id,
            "learner_id": candidate.student.learner_id,
            "first_name": candidate.student.first_name,
            "last_name": candidate.student.last_name,
            "date_of_birth": candidate.student.date_of_birth.isoformat() if candidate.student.date_of_birth else "",
            "centre_code": candidate.centre.code if candidate.centre_id else "",
            "status": candidate.status,
            "subject_codes": subject_codes,
            "board_reference": candidate.board_reference,
        }


def candidate_export_csv(session: ExternalExamSession) -> str:
    stream = io.StringIO()
    fieldnames = [
        "candidate_number",
        "student_id",
        "learner_id",
        "first_name",
        "last_name",
        "date_of_birth",
        "centre_code",
        "status",
        "subject_codes",
        "board_reference",
    ]
    writer = csv.DictWriter(stream, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(candidate_export_rows(session))
    return stream.getvalue()


def _decimal_value(value, field_name, row_number, errors, *, minimum=None, maximum=None):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = Decimal(raw)
    except InvalidOperation:
        errors.append(f"Row {row_number}: {field_name} must be a number.")
        return None
    if minimum is not None and parsed < minimum:
        errors.append(f"Row {row_number}: {field_name} cannot be below {minimum}.")
    if maximum is not None and parsed > maximum:
        errors.append(f"Row {row_number}: {field_name} cannot exceed {maximum}.")
    return parsed


def import_external_results(session: ExternalExamSession, uploaded_file, *, dry_run=True, user=None) -> dict:
    file_name = getattr(uploaded_file, "name", "external-results.csv")
    payload = uploaded_file.read()
    if isinstance(payload, bytes):
        try:
            text = payload.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValidationError("The result file must be UTF-8 encoded CSV.") from exc
    else:
        text = str(payload)
    reader = csv.DictReader(io.StringIO(text))
    required = {"candidate_number", "subject_code"}
    headers = set(reader.fieldnames or [])
    missing_headers = sorted(required - headers)
    if missing_headers:
        raise ValidationError(f"Missing required CSV column(s): {', '.join(missing_headers)}.")

    valid_statuses = {choice[0] for choice in ExternalExamResult.STATUS_CHOICES}
    prepared = []
    errors = []
    row_count = 0
    for row_number, row in enumerate(reader, start=2):
        row_count += 1
        candidate_number = str(row.get("candidate_number") or "").strip().upper()
        subject_code = str(row.get("subject_code") or "").strip().upper()
        registration = ExternalCandidateSubject.objects.filter(
            candidate__session=session,
            candidate__candidate_number=candidate_number,
            subject__subject_code=subject_code,
        ).select_related("candidate", "subject").first()
        if not registration:
            errors.append(
                f"Row {row_number}: no candidate-subject registration matches {candidate_number}/{subject_code}."
            )
            continue
        score = _decimal_value(row.get("score"), "score", row_number, errors, minimum=Decimal("0"))
        percentage = _decimal_value(
            row.get("percentage"),
            "percentage",
            row_number,
            errors,
            minimum=Decimal("0"),
            maximum=Decimal("100"),
        )
        if percentage is None and score is not None and registration.subject.max_score:
            percentage = (score / registration.subject.max_score * Decimal("100")).quantize(Decimal("0.01"))
        result_status = str(row.get("result_status") or ExternalExamResult.PENDING).strip().upper()
        if result_status not in valid_statuses:
            errors.append(f"Row {row_number}: invalid result_status '{result_status}'.")
            continue
        prepared.append(
            {
                "registration": registration,
                "score": score,
                "percentage": percentage,
                "grade": str(row.get("grade") or "").strip().upper(),
                "result_status": result_status,
                "source_reference": str(row.get("source_reference") or "").strip(),
                "raw_data": dict(row),
            }
        )

    accepted_count = len(prepared)
    rejected_count = row_count - accepted_count
    if not dry_run and errors:
        batch = ExternalResultImportBatch.objects.create(
            session=session,
            file_name=file_name,
            dry_run=False,
            row_count=row_count,
            accepted_count=0,
            rejected_count=row_count,
            errors=errors,
            imported_by=user,
        )
        return {
            "batch": batch,
            "row_count": row_count,
            "accepted_count": 0,
            "rejected_count": row_count,
            "errors": errors,
            "dry_run": False,
            "committed": False,
        }

    with transaction.atomic():
        if not dry_run:
            for item in prepared:
                ExternalExamResult.objects.update_or_create(
                    candidate_subject=item["registration"],
                    defaults={
                        "score": item["score"],
                        "percentage": item["percentage"],
                        "grade": item["grade"],
                        "result_status": item["result_status"],
                        "source_reference": item["source_reference"],
                        "is_official": True,
                        "released_at": timezone.now(),
                        "imported_by": user,
                        "raw_data": item["raw_data"],
                    },
                )
        batch = ExternalResultImportBatch.objects.create(
            session=session,
            file_name=file_name,
            dry_run=bool(dry_run),
            row_count=row_count,
            accepted_count=accepted_count,
            rejected_count=rejected_count,
            errors=errors,
            imported_by=user,
        )
    return {
        "batch": batch,
        "row_count": row_count,
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "errors": errors,
        "dry_run": bool(dry_run),
        "committed": not dry_run,
    }
