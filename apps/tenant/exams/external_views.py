from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .external_forms import (
    ExternalCandidateForm,
    ExternalCandidateSubjectForm,
    ExternalExamBoardForm,
    ExternalExamCentreForm,
    ExternalExamSessionForm,
    ExternalExamSubjectForm,
    ExternalResultImportForm,
)
from .external_models import (
    ExternalCandidate,
    ExternalCandidateSubject,
    ExternalExamBoard,
    ExternalExamCentre,
    ExternalExamSession,
    ExternalExamSubject,
)
from .external_services import (
    candidate_export_csv,
    candidate_registration_preview,
    compulsory_subject_preview,
    external_exam_readiness,
    import_external_results,
    register_compulsory_subjects,
    register_eligible_candidates,
    session_errors,
)


def _form_page(request, *, form, title, back_url_name, back_url_kwargs=None):
    return render(
        request,
        "portals/admin/exams/external/form.html",
        {
            "form": form,
            "title": title,
            "back_url_name": back_url_name,
            "back_url_kwargs": back_url_kwargs or {},
        },
    )


@role_required(Role.ADMIN)
def external_exam_dashboard(request):
    readiness = external_exam_readiness()
    boards = ExternalExamBoard.objects.prefetch_related("centres", "sessions").order_by("name")
    sessions = ExternalExamSession.objects.select_related(
        "board", "centre", "academic_year", "campus", "stage", "level", "program", "linked_exam"
    ).prefetch_related("subjects", "candidates").order_by("-academic_year__name", "board__name", "name")
    return render(
        request,
        "portals/admin/exams/external/dashboard.html",
        {"readiness": readiness, "boards": boards, "sessions": sessions},
    )


@role_required(Role.ADMIN)
def board_create(request):
    if request.method == "POST":
        form = ExternalExamBoardForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "External examination board created.")
            return redirect("admin_external_exam_dashboard")
    else:
        form = ExternalExamBoardForm()
    return _form_page(
        request,
        form=form,
        title="Add external examination board",
        back_url_name="admin_external_exam_dashboard",
    )


@role_required(Role.ADMIN)
def board_edit(request, pk: int):
    board = get_object_or_404(ExternalExamBoard, pk=pk)
    if request.method == "POST":
        form = ExternalExamBoardForm(request.POST, instance=board)
        if form.is_valid():
            form.save()
            messages.success(request, "External examination board updated.")
            return redirect("admin_external_exam_dashboard")
    else:
        form = ExternalExamBoardForm(instance=board)
    return _form_page(
        request,
        form=form,
        title="Edit external examination board",
        back_url_name="admin_external_exam_dashboard",
    )


@role_required(Role.ADMIN)
def centre_create(request):
    if request.method == "POST":
        form = ExternalExamCentreForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "External examination centre created.")
            return redirect("admin_external_exam_dashboard")
    else:
        form = ExternalExamCentreForm()
    return _form_page(
        request,
        form=form,
        title="Add external examination centre",
        back_url_name="admin_external_exam_dashboard",
    )


@role_required(Role.ADMIN)
def centre_edit(request, pk: int):
    centre = get_object_or_404(ExternalExamCentre, pk=pk)
    if request.method == "POST":
        form = ExternalExamCentreForm(request.POST, instance=centre)
        if form.is_valid():
            form.save()
            messages.success(request, "External examination centre updated.")
            return redirect("admin_external_exam_dashboard")
    else:
        form = ExternalExamCentreForm(instance=centre)
    return _form_page(
        request,
        form=form,
        title="Edit external examination centre",
        back_url_name="admin_external_exam_dashboard",
    )


@role_required(Role.ADMIN)
def session_create(request):
    if request.method == "POST":
        form = ExternalExamSessionForm(request.POST)
        if form.is_valid():
            session = form.save()
            messages.success(request, "External examination session created. Add its registered subjects next.")
            return redirect("admin_external_exam_session_detail", pk=session.pk)
    else:
        form = ExternalExamSessionForm()
    return _form_page(
        request,
        form=form,
        title="Add external examination session",
        back_url_name="admin_external_exam_dashboard",
    )


@role_required(Role.ADMIN)
def session_edit(request, pk: int):
    session = get_object_or_404(ExternalExamSession, pk=pk)
    if request.method == "POST":
        form = ExternalExamSessionForm(request.POST, instance=session)
        if form.is_valid():
            form.save()
            messages.success(request, "External examination session updated.")
            return redirect("admin_external_exam_session_detail", pk=session.pk)
    else:
        form = ExternalExamSessionForm(instance=session)
    return _form_page(
        request,
        form=form,
        title="Edit external examination session",
        back_url_name="admin_external_exam_session_detail",
        back_url_kwargs={"pk": session.pk},
    )


@role_required(Role.ADMIN)
def session_detail(request, pk: int):
    session = get_object_or_404(
        ExternalExamSession.objects.select_related(
            "board", "centre", "academic_year", "campus", "stage", "level", "program", "linked_exam"
        ).prefetch_related("subjects__course", "candidates"),
        pk=pk,
    )
    return render(
        request,
        "portals/admin/exams/external/session_detail.html",
        {
            "session": session,
            "subjects": session.subjects.select_related("course", "linked_paper").order_by("order", "pk"),
            "errors": session_errors(session),
            "candidate_preview": candidate_registration_preview(session),
            "compulsory_preview": compulsory_subject_preview(session),
            "recent_imports": session.result_import_batches.select_related("imported_by")[:5],
        },
    )


@role_required(Role.ADMIN)
def subject_create(request, session_pk: int):
    session = get_object_or_404(ExternalExamSession, pk=session_pk)
    if request.method == "POST":
        form = ExternalExamSubjectForm(request.POST, session=session)
        if form.is_valid():
            form.save()
            messages.success(request, "External examination subject added.")
            return redirect("admin_external_exam_session_detail", pk=session.pk)
    else:
        form = ExternalExamSubjectForm(session=session)
    return _form_page(
        request,
        form=form,
        title=f"Add subject to {session.name}",
        back_url_name="admin_external_exam_session_detail",
        back_url_kwargs={"pk": session.pk},
    )


@role_required(Role.ADMIN)
def subject_edit(request, pk: int):
    subject = get_object_or_404(ExternalExamSubject.objects.select_related("session"), pk=pk)
    if request.method == "POST":
        form = ExternalExamSubjectForm(request.POST, instance=subject, session=subject.session)
        if form.is_valid():
            form.save()
            messages.success(request, "External examination subject updated.")
            return redirect("admin_external_exam_session_detail", pk=subject.session_id)
    else:
        form = ExternalExamSubjectForm(instance=subject, session=subject.session)
    return _form_page(
        request,
        form=form,
        title="Edit external examination subject",
        back_url_name="admin_external_exam_session_detail",
        back_url_kwargs={"pk": subject.session_id},
    )


@role_required(Role.ADMIN)
def session_candidates(request, pk: int):
    session = get_object_or_404(
        ExternalExamSession.objects.select_related("board", "centre", "academic_year", "campus", "level", "program"),
        pk=pk,
    )
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "register_candidates":
                summary = register_eligible_candidates(session, dry_run=False)
                messages.success(request, f"Registered {summary['created_count']} new candidate(s).")
            elif action == "register_compulsory_subjects":
                summary = register_compulsory_subjects(session, dry_run=False)
                messages.success(request, f"Added {summary['created_count']} compulsory subject registration(s).")
            else:
                messages.error(request, "Unknown candidate registration action.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        return redirect("admin_external_exam_candidates", pk=session.pk)

    candidates = session.candidates.select_related("student", "centre").prefetch_related(
        "subject_registrations__subject"
    ).order_by("candidate_number")
    return render(
        request,
        "portals/admin/exams/external/candidates.html",
        {
            "session": session,
            "candidates": candidates,
            "candidate_preview": candidate_registration_preview(session),
            "compulsory_preview": compulsory_subject_preview(session),
        },
    )


@role_required(Role.ADMIN)
def candidate_create(request, session_pk: int):
    session = get_object_or_404(ExternalExamSession, pk=session_pk)
    if request.method == "POST":
        form = ExternalCandidateForm(request.POST, session=session)
        if form.is_valid():
            candidate = form.save()
            messages.success(request, "External examination candidate registered.")
            return redirect("admin_external_exam_candidate_detail", pk=candidate.pk)
    else:
        form = ExternalCandidateForm(session=session)
    return _form_page(
        request,
        form=form,
        title=f"Register candidate — {session.name}",
        back_url_name="admin_external_exam_candidates",
        back_url_kwargs={"pk": session.pk},
    )


@role_required(Role.ADMIN)
def candidate_edit(request, pk: int):
    candidate = get_object_or_404(ExternalCandidate.objects.select_related("session"), pk=pk)
    if request.method == "POST":
        form = ExternalCandidateForm(request.POST, instance=candidate, session=candidate.session)
        if form.is_valid():
            form.save()
            messages.success(request, "Candidate registration updated.")
            return redirect("admin_external_exam_candidate_detail", pk=candidate.pk)
    else:
        form = ExternalCandidateForm(instance=candidate, session=candidate.session)
    return _form_page(
        request,
        form=form,
        title="Edit external examination candidate",
        back_url_name="admin_external_exam_candidate_detail",
        back_url_kwargs={"pk": candidate.pk},
    )


@role_required(Role.ADMIN)
def candidate_detail(request, pk: int):
    candidate = get_object_or_404(
        ExternalCandidate.objects.select_related("session", "session__board", "student", "centre").prefetch_related(
            "subject_registrations__subject__course",
            "subject_registrations__official_result",
        ),
        pk=pk,
    )
    return render(
        request,
        "portals/admin/exams/external/candidate_detail.html",
        {
            "candidate": candidate,
            "registrations": candidate.subject_registrations.select_related(
                "subject__course", "official_result"
            ).order_by("subject__order", "subject__subject_code"),
        },
    )


@role_required(Role.ADMIN)
def candidate_subject_add(request, candidate_pk: int):
    candidate = get_object_or_404(ExternalCandidate.objects.select_related("session"), pk=candidate_pk)
    if request.method == "POST":
        form = ExternalCandidateSubjectForm(request.POST, candidate=candidate)
        if form.is_valid():
            form.save()
            messages.success(request, "Candidate subject registered.")
            return redirect("admin_external_exam_candidate_detail", pk=candidate.pk)
    else:
        form = ExternalCandidateSubjectForm(candidate=candidate)
    return _form_page(
        request,
        form=form,
        title=f"Add subject — {candidate.candidate_number}",
        back_url_name="admin_external_exam_candidate_detail",
        back_url_kwargs={"pk": candidate.pk},
    )


@role_required(Role.ADMIN)
def candidate_subject_edit(request, pk: int):
    registration = get_object_or_404(
        ExternalCandidateSubject.objects.select_related("candidate", "candidate__session"),
        pk=pk,
    )
    if request.method == "POST":
        form = ExternalCandidateSubjectForm(request.POST, instance=registration, candidate=registration.candidate)
        if form.is_valid():
            form.save()
            messages.success(request, "Candidate subject registration updated.")
            return redirect("admin_external_exam_candidate_detail", pk=registration.candidate_id)
    else:
        form = ExternalCandidateSubjectForm(instance=registration, candidate=registration.candidate)
    return _form_page(
        request,
        form=form,
        title="Edit candidate subject registration",
        back_url_name="admin_external_exam_candidate_detail",
        back_url_kwargs={"pk": registration.candidate_id},
    )


@role_required(Role.ADMIN)
def export_candidates(request, pk: int):
    session = get_object_or_404(ExternalExamSession, pk=pk)
    response = HttpResponse(candidate_export_csv(session), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{session.code.lower()}-candidates.csv"'
    return response


@role_required(Role.ADMIN)
def import_results(request, pk: int):
    session = get_object_or_404(ExternalExamSession.objects.select_related("board", "academic_year"), pk=pk)
    summary = None
    if request.method == "POST":
        form = ExternalResultImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                summary = import_external_results(
                    session,
                    form.cleaned_data["csv_file"],
                    dry_run=form.cleaned_data["dry_run"],
                    user=request.user,
                )
                if summary["committed"]:
                    messages.success(request, f"Imported {summary['accepted_count']} official external result(s).")
                else:
                    messages.info(
                        request,
                        f"Dry run complete: {summary['accepted_count']} accepted, {summary['rejected_count']} rejected.",
                    )
            except ValidationError as exc:
                form.add_error("csv_file", " ".join(exc.messages))
    else:
        form = ExternalResultImportForm(initial={"dry_run": True})
    return render(
        request,
        "portals/admin/exams/external/import_results.html",
        {"session": session, "form": form, "summary": summary},
    )
