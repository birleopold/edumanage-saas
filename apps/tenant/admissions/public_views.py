from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization

from .forms import PublicApplicantForm, PublicTrackingForm
from .models import AdmissionAppointment, Applicant, ApplicantDocument, ApplicantPayment


def _campus_queryset():
    org = get_or_create_organization()
    return Campus.objects.filter(organization=org).order_by("name")


def public_application_create(request):
    campuses = _campus_queryset()
    if request.method == "POST":
        form = PublicApplicantForm(request.POST, request.FILES, campuses=campuses)
        if form.is_valid():
            applicant = form.save(commit=False)
            applicant.status = Applicant.NEW
            applicant.source = Applicant.SOURCE_ONLINE
            applicant.submitted_online = True
            applicant.custom_responses = form.custom_responses()
            applicant.save()
            uploaded_file = form.cleaned_data.get("supporting_document")
            if uploaded_file:
                ApplicantDocument.objects.create(
                    applicant=applicant,
                    title=form.cleaned_data.get("document_title") or "Supporting document",
                    file=uploaded_file,
                )
            messages.success(request, "Application submitted successfully. Please save your application reference.")
            return redirect("public_admissions_success", reference=applicant.application_reference)
    else:
        form = PublicApplicantForm(campuses=campuses)
    return render(request, "portals/public/admissions/apply.html", {"form": form})


def _public_applicant_queryset():
    return Applicant.objects.select_related(
        "campus",
        "target_term",
        "target_term__year",
        "target_level",
        "target_program",
        "target_class_group",
        "created_student",
        "created_admission_invoice",
    ).prefetch_related("appointments", "communications", "admission_payments", "documents")


def _tracker_step(title: str, state: str, detail: str) -> dict:
    return {"title": title, "state": state, "detail": detail}


def _build_public_tracker(applicant: Applicant) -> dict:
    documents = list(applicant.documents.all())
    appointments = list(applicant.appointments.all())
    payments = list(applicant.admission_payments.all())
    next_appointment = next((item for item in appointments if item.status == AdmissionAppointment.SCHEDULED), None)
    completed_appointment = any(item.status == AdmissionAppointment.COMPLETED for item in appointments)
    invoice = applicant.created_admission_invoice
    invoice_balance = invoice.balance() if invoice else None
    paid_or_waived = any(item.status in {ApplicantPayment.PAID, ApplicantPayment.WAIVED} for item in payments)
    pending_payment = next((item for item in payments if item.status == ApplicantPayment.PENDING), None)

    if documents:
        document_state = "complete"
        document_detail = f"{len(documents)} supporting document(s) received."
    else:
        document_state = "current"
        document_detail = "Upload or submit the requested documents to the admissions office."

    if completed_appointment:
        interview_state = "complete"
        interview_detail = "Interview or admission test completed."
    elif next_appointment:
        interview_state = "current"
        interview_detail = f"{next_appointment.get_appointment_type_display()} scheduled for {next_appointment.scheduled_at}."
    elif applicant.status in {Applicant.IN_REVIEW, Applicant.ADMITTED, Applicant.REJECTED}:
        interview_state = "current"
        interview_detail = "The admissions team will confirm whether an interview or test is needed."
    else:
        interview_state = "pending"
        interview_detail = "Waiting for admissions review."

    if applicant.status == Applicant.ADMITTED:
        decision_state = "complete"
        decision_detail = "Application admitted."
    elif applicant.status == Applicant.REJECTED:
        decision_state = "problem"
        decision_detail = "Application not admitted."
    elif applicant.status == Applicant.IN_REVIEW:
        decision_state = "current"
        decision_detail = "Application is under review."
    else:
        decision_state = "pending"
        decision_detail = "Application submitted and waiting for review."

    if invoice and invoice_balance is not None and invoice_balance <= 0:
        payment_state = "complete"
        payment_detail = "Admission invoice is fully settled."
    elif paid_or_waived:
        payment_state = "complete"
        payment_detail = "Admission payment has been recorded."
    elif invoice:
        payment_state = "current"
        payment_detail = f"Admission invoice {invoice.reference or invoice.id} has balance {invoice_balance}."
    elif pending_payment:
        payment_state = "current"
        payment_detail = f"Payment request {pending_payment.reference or pending_payment.id} is pending."
    else:
        payment_state = "pending"
        payment_detail = "No payment request has been issued yet."

    return {
        "steps": [
            _tracker_step("Submitted application", "complete", "Application reference created."),
            _tracker_step("Required documents", document_state, document_detail),
            _tracker_step("Interview or test", interview_state, interview_detail),
            _tracker_step("Admission decision", decision_state, decision_detail),
            _tracker_step("Payment instructions", payment_state, payment_detail),
        ],
        "documents": documents,
        "appointments": appointments,
        "payments": payments,
        "next_appointment": next_appointment,
        "invoice": invoice,
        "invoice_balance": invoice_balance,
        "payment_instruction": payment_detail,
        "required_documents": [
            "Birth certificate or learner ID",
            "Previous school report",
            "Guardian contact details",
        ],
    }


def public_application_success(request, reference: str):
    applicant = get_object_or_404(_public_applicant_queryset(), application_reference=reference)
    return render(
        request,
        "portals/public/admissions/success.html",
        {"applicant": applicant, "tracker": _build_public_tracker(applicant)},
    )


def public_application_track(request):
    applicant = None
    form = PublicTrackingForm(request.GET or None)
    if request.GET and form.is_valid():
        reference = form.cleaned_data["reference"].strip().upper()
        contact = (form.cleaned_data.get("contact") or "").strip()
        qs = _public_applicant_queryset().filter(application_reference__iexact=reference)
        if contact:
            qs = qs.filter(Q(email__iexact=contact) | Q(phone__icontains=contact))
        applicant = qs.first()
        if not applicant:
            messages.error(request, "No application matched those details. Check the reference and contact used during application.")
    tracker = _build_public_tracker(applicant) if applicant else None
    return render(request, "portals/public/admissions/track.html", {"form": form, "applicant": applicant, "tracker": tracker})
