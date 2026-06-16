from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_current_campus, get_or_create_organization
from apps.tenant.portals.permissions import admin_portal_required
from apps.tenant.orgsettings.utils import log_action

from .forms import AdmissionDecisionForm, ApplicantConversionForm, ApplicantForm
from .models import Applicant
from .pdf_letter import generate_admission_letter_pdf
from .services import convert_applicant_to_student, pipeline_summary


def _parse_per_page(request, default: int = 25, max_value: int = 200) -> int:
    per_page_raw = request.GET.get("per_page")
    per_page = default
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = default
    return max(1, min(per_page, max_value))


def _campus_queryset():
    org = get_or_create_organization()
    return Campus.objects.filter(organization=org).order_by("name")


def _applicant_queryset():
    return Applicant.objects.select_related(
        "campus",
        "target_term",
        "target_term__year",
        "target_level",
        "target_program",
        "target_class_group",
        "created_student",
    ).prefetch_related("documents")


def _filter_applicants(request, qs):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    source = (request.GET.get("source") or "").strip()
    campus_raw = (request.GET.get("campus") or "").strip()

    if q:
        qs = qs.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(application_reference__icontains=q)
            | Q(email__icontains=q)
            | Q(phone__icontains=q)
            | Q(guardian_name__icontains=q)
        )
    if status in dict(Applicant.STATUS_CHOICES):
        qs = qs.filter(status=status)
    if source in dict(Applicant.SOURCE_CHOICES):
        qs = qs.filter(source=source)
    if campus_raw.isdigit():
        qs = qs.filter(campus_id=int(campus_raw))
    return qs, q, status, source, int(campus_raw) if campus_raw.isdigit() else None


@admin_portal_required
def applicant_list(request):
    per_page = _parse_per_page(request)
    page_number = request.GET.get("page") or 1

    qs, q, status, source, campus_id = _filter_applicants(request, _applicant_queryset().all())
    all_for_summary = _applicant_queryset().all()
    summary = pipeline_summary(all_for_summary)

    page_obj = Paginator(qs, per_page).get_page(page_number)

    return render(
        request,
        "portals/admin/admissions/applicants_list.html",
        {
            "applicants": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "status": status,
            "source": source,
            "selected_campus_id": campus_id,
            "per_page": per_page,
            "summary": summary,
            "campuses": _campus_queryset(),
            "status_choices": Applicant.STATUS_CHOICES,
            "source_choices": Applicant.SOURCE_CHOICES,
        },
    )


@admin_portal_required
def applicant_pipeline(request):
    qs, q, status, source, campus_id = _filter_applicants(request, _applicant_queryset().all())
    applicants = list(qs)
    columns = [
        (Applicant.NEW, "New", [a for a in applicants if a.status == Applicant.NEW]),
        (Applicant.IN_REVIEW, "In review", [a for a in applicants if a.status == Applicant.IN_REVIEW]),
        (Applicant.ADMITTED, "Admitted", [a for a in applicants if a.status == Applicant.ADMITTED]),
        (Applicant.REJECTED, "Rejected", [a for a in applicants if a.status == Applicant.REJECTED]),
    ]

    return render(
        request,
        "portals/admin/admissions/pipeline.html",
        {
            "columns": columns,
            "q": q,
            "status": status,
            "source": source,
            "selected_campus_id": campus_id,
            "campuses": _campus_queryset(),
            "status_choices": Applicant.STATUS_CHOICES,
            "source_choices": Applicant.SOURCE_CHOICES,
            "summary": pipeline_summary(applicants),
        },
    )


@admin_portal_required
def applicant_create(request):
    campuses = _campus_queryset()
    current = get_current_campus(request)

    if request.method == "POST":
        form = ApplicantForm(request.POST, campuses=campuses)
        if form.is_valid():
            applicant = form.save(commit=False)
            if applicant.campus_id is None and current is not None:
                applicant.campus = current
            applicant.save()
            messages.success(request, "Applicant created.")
            return redirect("admin_admissions_applicant_detail", pk=applicant.pk)
    else:
        form = ApplicantForm(campuses=campuses)
        if current is not None:
            form.fields["campus"].initial = current

    return render(request, "portals/admin/admissions/applicant_form.html", {"form": form, "mode": "create"})


@admin_portal_required
def applicant_edit(request, pk: int):
    campuses = _campus_queryset()
    applicant = get_object_or_404(Applicant, pk=pk)

    if request.method == "POST":
        form = ApplicantForm(request.POST, instance=applicant, campuses=campuses)
        if form.is_valid():
            form.save()
            messages.success(request, "Applicant updated.")
            return redirect("admin_admissions_applicant_detail", pk=applicant.pk)
    else:
        form = ApplicantForm(instance=applicant, campuses=campuses)

    return render(
        request,
        "portals/admin/admissions/applicant_form.html",
        {"form": form, "mode": "edit", "applicant": applicant},
    )


@admin_portal_required
def applicant_detail(request, pk: int):
    applicant = get_object_or_404(_applicant_queryset(), pk=pk)
    decision_form = AdmissionDecisionForm(initial={"status": applicant.status})
    conversion_form = ApplicantConversionForm(applicant=applicant, campuses=_campus_queryset())
    if applicant.campus_id:
        conversion_form.fields["campus"].initial = applicant.campus
    return render(
        request,
        "portals/admin/admissions/applicant_detail.html",
        {
            "applicant": applicant,
            "decision_form": decision_form,
            "conversion_form": conversion_form,
        },
    )


@admin_portal_required
def applicant_set_status(request, pk: int):
    applicant = get_object_or_404(Applicant, pk=pk)
    if request.method != "POST":
        return redirect("admin_admissions_applicant_detail", pk=applicant.pk)

    form = AdmissionDecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Invalid admission decision.")
        return redirect("admin_admissions_applicant_detail", pk=applicant.pk)

    status = form.cleaned_data["status"]
    note = (form.cleaned_data.get("note") or "").strip()
    if applicant.status == Applicant.ADMITTED and applicant.created_student_id and status != Applicant.ADMITTED:
        messages.error(request, "This applicant has already been converted to a student and cannot be moved backwards.")
        return redirect("admin_admissions_applicant_detail", pk=applicant.pk)

    applicant.status = status
    if note:
        applicant.note = (applicant.note + "\n" if applicant.note else "") + note
        applicant.save(update_fields=["status", "note", "updated_at"])
    else:
        applicant.save(update_fields=["status", "updated_at"])

    messages.success(request, "Admission decision updated.")
    return redirect("admin_admissions_applicant_detail", pk=applicant.pk)


@admin_portal_required
def applicant_reject(request, pk: int):
    applicant = get_object_or_404(Applicant, pk=pk)
    if request.method != "POST":
        return render(request, "portals/admin/admissions/reject_confirm.html", {"applicant": applicant})

    note = (request.POST.get("note") or "").strip()
    if applicant.created_student_id:
        messages.error(request, "This applicant has already been converted to a student and cannot be rejected.")
        return redirect("admin_admissions_applicant_detail", pk=applicant.pk)
    applicant.status = Applicant.REJECTED
    if note:
        applicant.note = (applicant.note + "\n" if applicant.note else "") + f"Rejection note: {note}"
        applicant.save(update_fields=["status", "note", "updated_at"])
    else:
        applicant.save(update_fields=["status", "updated_at"])
    messages.success(request, "Applicant rejected.")
    return redirect("admin_admissions_applicant_detail", pk=applicant.pk)


@admin_portal_required
def applicant_admit(request, pk: int):
    applicant = get_object_or_404(Applicant.objects.select_related("created_student", "campus", "target_class_group"), pk=pk)
    campuses = _campus_queryset()

    if applicant.status == Applicant.ADMITTED and applicant.created_student_id:
        messages.info(request, "Applicant already converted to a student.")
        return redirect("admin_admissions_applicant_detail", pk=applicant.pk)

    if request.method == "POST":
        form = ApplicantConversionForm(request.POST, applicant=applicant, campuses=campuses)
        if form.is_valid():
            try:
                result = convert_applicant_to_student(
                    applicant=applicant,
                    campus=form.cleaned_data["campus"],
                    stream=form.cleaned_data.get("stream"),
                    student_id=form.cleaned_data.get("student_id"),
                    create_student_login=form.cleaned_data.get("create_student_login"),
                    create_parent_link=form.cleaned_data.get("create_parent_link"),
                    send_credentials_email_flag=form.cleaned_data.get("send_credentials_email"),
                )
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                log_action(
                    result.student,
                    action="APPLICANT_CONVERTED_TO_STUDENT",
                    description=f"Applicant {applicant.application_reference} converted to student {result.student.student_id}.",
                    user=request.user,
                    metadata={"applicant_id": applicant.pk, "credentials_sent": result.credentials_sent},
                )
                if result.credentials_sent:
                    messages.success(request, "Applicant admitted, student profile created, and login details sent by email.")
                elif result.user:
                    messages.success(request, "Applicant admitted and student profile created. Login was created but email was not sent.")
                else:
                    messages.success(request, "Applicant admitted and student profile created.")
                return redirect("admin_admissions_applicant_detail", pk=applicant.pk)
    else:
        form = ApplicantConversionForm(applicant=applicant, campuses=campuses)
        if applicant.campus_id:
            form.fields["campus"].initial = applicant.campus

    return render(
        request,
        "portals/admin/admissions/convert_to_student.html",
        {"applicant": applicant, "form": form},
    )


@admin_portal_required
def applicant_admission_letter_pdf(request, pk: int):
    applicant = get_object_or_404(
        Applicant.objects.select_related("created_student", "campus", "target_term"),
        pk=pk,
    )
    if applicant.status != Applicant.ADMITTED or not applicant.created_student_id:
        return HttpResponseForbidden(
            "This letter is only available after admission, once a student record exists."
        )
    student = applicant.created_student
    org = get_or_create_organization()
    buf = generate_admission_letter_pdf(
        applicant=applicant,
        student=student,
        org=org,
        issued_by=request.user.get_full_name() or request.user.get_username(),
    )
    log_action(
        applicant,
        action="ADMISSION_LETTER_PDF",
        description=f"Admission letter PDF generated for student {student.student_id}.",
        user=request.user,
        metadata={"student_profile_id": student.pk},
    )
    response = HttpResponse(buf.read(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="admission_{applicant.pk}.pdf"'
    return response
