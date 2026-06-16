from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization

from .forms import PublicApplicantForm, PublicTrackingForm
from .models import Applicant, ApplicantDocument


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
    ).prefetch_related("appointments", "communications", "admission_payments")


def public_application_success(request, reference: str):
    applicant = get_object_or_404(_public_applicant_queryset(), application_reference=reference)
    return render(request, "portals/public/admissions/success.html", {"applicant": applicant})


def public_application_track(request):
    applicant = None
    form = PublicTrackingForm(request.GET or None)
    if request.GET and form.is_valid():
        reference = form.cleaned_data["reference"].strip().upper()
        contact = (form.cleaned_data.get("contact") or "").strip().lower()
        qs = _public_applicant_queryset().filter(application_reference__iexact=reference)
        if contact:
            qs = qs.filter(email__iexact=contact) | _public_applicant_queryset().filter(application_reference__iexact=reference, phone__icontains=contact)
        applicant = qs.first()
        if not applicant:
            messages.error(request, "No application matched those details. Check the reference and contact used during application.")
    return render(request, "portals/public/admissions/track.html", {"form": form, "applicant": applicant})
