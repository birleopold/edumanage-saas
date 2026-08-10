from __future__ import annotations

import copy
import io
import secrets
from datetime import date, datetime
from decimal import Decimal
from xml.sax.saxutils import escape

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

from apps.tenant.orgsettings.models import OrganizationProfile

from .models import DocumentTemplate, DocumentTemplateVersion, IssuedDocument
from .schema import validate_design_document


def _json_value(value):
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def page_dimensions_for(document_type: str) -> tuple[float, float]:
    if document_type == DocumentTemplate.STUDENT_ID:
        return 85.60, 54.00
    if document_type in {DocumentTemplate.LEAVERS_CERTIFICATE, DocumentTemplate.CERTIFICATE}:
        return 297.00, 210.00
    return 210.00, 297.00


def default_design(document_type: str) -> dict:
    width, height = page_dimensions_for(document_type)
    if document_type == DocumentTemplate.STUDENT_ID:
        elements = [
            {"id": "school-name", "type": "field", "binding": "school.name", "x": 20, "y": 5, "width": 60, "height": 7, "fontSize": 12, "fontFamily": "Helvetica", "bold": True, "align": "center", "color": "#0F172A"},
            {"id": "school-logo", "type": "image", "binding": "school.logo", "x": 4, "y": 4, "width": 13, "height": 13},
            {"id": "student-photo", "type": "image", "binding": "student.photo", "x": 5, "y": 18, "width": 22, "height": 27, "borderColor": "#CBD5E1", "borderWidth": 0.4},
            {"id": "student-name", "type": "field", "binding": "student.full_name", "x": 31, "y": 19, "width": 49, "height": 8, "fontSize": 13, "fontFamily": "Helvetica", "bold": True, "color": "#0F172A"},
            {"id": "student-number", "type": "field", "binding": "student.student_id", "prefix": "ID: ", "x": 31, "y": 29, "width": 32, "height": 6, "fontSize": 8, "fontFamily": "Helvetica", "color": "#334155"},
            {"id": "student-class", "type": "field", "binding": "student.class", "prefix": "Class: ", "x": 31, "y": 36, "width": 32, "height": 6, "fontSize": 8, "fontFamily": "Helvetica", "color": "#334155"},
            {"id": "verify-qr", "type": "qr", "binding": "document.verification_url", "x": 66, "y": 30, "width": 14, "height": 14},
            {"id": "accent", "type": "rectangle", "x": 0, "y": 49, "width": 85.6, "height": 5, "backgroundColor": "#1E3A8A", "borderColor": "#1E3A8A", "borderWidth": 0},
        ]
    elif document_type == DocumentTemplate.REPORT_CARD:
        elements = [
            {"id": "school-name", "type": "field", "binding": "school.name", "x": 25, "y": 10, "width": 160, "height": 10, "fontSize": 18, "fontFamily": "Helvetica", "bold": True, "align": "center", "color": "#0F172A"},
            {"id": "school-logo", "type": "image", "binding": "school.logo", "x": 10, "y": 8, "width": 18, "height": 18},
            {"id": "title", "type": "text", "text": "LEARNER PROGRESS REPORT", "x": 25, "y": 24, "width": 160, "height": 8, "fontSize": 12, "fontFamily": "Helvetica", "bold": True, "align": "center", "color": "#1E3A8A"},
            {"id": "student-name", "type": "field", "binding": "student.full_name", "prefix": "Learner: ", "x": 12, "y": 39, "width": 92, "height": 7, "fontSize": 10, "fontFamily": "Helvetica", "bold": True, "color": "#0F172A"},
            {"id": "class", "type": "field", "binding": "student.class", "prefix": "Class: ", "x": 108, "y": 39, "width": 42, "height": 7, "fontSize": 9, "fontFamily": "Helvetica", "color": "#334155"},
            {"id": "term", "type": "field", "binding": "academic.term", "prefix": "Term: ", "x": 151, "y": 39, "width": 47, "height": 7, "fontSize": 9, "fontFamily": "Helvetica", "color": "#334155"},
            {"id": "results", "type": "results_table", "x": 12, "y": 52, "width": 186, "height": 150, "fontSize": 8, "fontFamily": "Helvetica", "color": "#0F172A", "headerColor": "#1E3A8A"},
            {"id": "mean", "type": "field", "binding": "academic.mean", "prefix": "Mean: ", "x": 12, "y": 210, "width": 45, "height": 7, "fontSize": 10, "fontFamily": "Helvetica", "bold": True, "color": "#0F172A"},
            {"id": "grade", "type": "field", "binding": "academic.overall_grade", "prefix": "Overall grade: ", "x": 62, "y": 210, "width": 55, "height": 7, "fontSize": 10, "fontFamily": "Helvetica", "bold": True, "color": "#0F172A"},
            {"id": "remark", "type": "field", "binding": "academic.overall_remark", "prefix": "Remark: ", "x": 12, "y": 224, "width": 145, "height": 18, "fontSize": 9, "fontFamily": "Helvetica", "color": "#334155"},
            {"id": "verify-qr", "type": "qr", "binding": "document.verification_url", "x": 166, "y": 220, "width": 25, "height": 25},
            {"id": "footer", "type": "text", "text": "Generated and verifiable through EduManage", "x": 20, "y": 278, "width": 170, "height": 6, "fontSize": 7, "fontFamily": "Helvetica", "align": "center", "color": "#64748B"},
        ]
    else:
        title = "LEAVERS CERTIFICATE" if document_type == DocumentTemplate.LEAVERS_CERTIFICATE else "OFFICIAL DOCUMENT"
        elements = [
            {"id": "border", "type": "rectangle", "x": 8, "y": 8, "width": width - 16, "height": height - 16, "backgroundColor": "transparent", "borderColor": "#1E3A8A", "borderWidth": 1.2},
            {"id": "school-logo", "type": "image", "binding": "school.logo", "x": width / 2 - 12, "y": 15, "width": 24, "height": 24},
            {"id": "school-name", "type": "field", "binding": "school.name", "x": 30, "y": 43, "width": width - 60, "height": 10, "fontSize": 18, "fontFamily": "Helvetica", "bold": True, "align": "center", "color": "#0F172A"},
            {"id": "title", "type": "text", "text": title, "x": 35, "y": 65, "width": width - 70, "height": 12, "fontSize": 22, "fontFamily": "Helvetica", "bold": True, "align": "center", "color": "#1E3A8A"},
            {"id": "certifies", "type": "text", "text": "This is to certify that", "x": 45, "y": 91, "width": width - 90, "height": 8, "fontSize": 12, "fontFamily": "Times-Roman", "align": "center", "color": "#334155"},
            {"id": "student-name", "type": "field", "binding": "student.full_name", "x": 35, "y": 108, "width": width - 70, "height": 12, "fontSize": 22, "fontFamily": "Helvetica", "bold": True, "align": "center", "color": "#0F172A"},
            {"id": "statement", "type": "text", "text": "was a registered learner of this institution and completed the required programme of study.", "x": 45, "y": 132, "width": width - 90, "height": 20, "fontSize": 12, "fontFamily": "Times-Roman", "align": "center", "color": "#334155"},
            {"id": "issue-date", "type": "field", "binding": "document.issue_date", "prefix": "Issued: ", "x": 45, "y": height - 45, "width": 70, "height": 8, "fontSize": 9, "fontFamily": "Helvetica", "color": "#334155"},
            {"id": "verify-qr", "type": "qr", "binding": "document.verification_url", "x": width - 60, "y": height - 55, "width": 30, "height": 30},
        ]
    return {"version": 1, "pages": [{"id": "page-1", "name": "Front", "elements": elements}]}


def create_template(name: str, document_type: str, user, **scope) -> DocumentTemplate:
    width, height = page_dimensions_for(document_type)
    with transaction.atomic():
        template = DocumentTemplate(name=name, document_type=document_type, created_by=user, updated_by=user, **scope)
        template.full_clean()
        template.save()
        DocumentTemplateVersion.objects.create(
            template=template,
            number=1,
            design=default_design(document_type),
            page_width_mm=width,
            page_height_mm=height,
            created_by=user,
        )
    return template


def get_editable_version(template: DocumentTemplate, user) -> DocumentTemplateVersion:
    latest = template.latest_version
    if latest and latest.status == DocumentTemplateVersion.DRAFT:
        return latest
    number = (latest.number if latest else 0) + 1
    if latest:
        design = copy.deepcopy(latest.design)
        width = latest.page_width_mm
        height = latest.page_height_mm
        fit = latest.background_fit
        background_name = latest.background.name
    else:
        design = default_design(template.document_type)
        width, height = page_dimensions_for(template.document_type)
        fit = DocumentTemplateVersion.FIT_COVER
        background_name = ""
    draft = DocumentTemplateVersion(
        template=template,
        number=number,
        design=design,
        page_width_mm=width,
        page_height_mm=height,
        background_fit=fit,
        created_by=user,
    )
    if background_name:
        draft.background.name = background_name
    draft.save()
    return draft


def save_draft(version: DocumentTemplateVersion, *, design: dict, width: float, height: float, background=None, background_fit=None, notes=""):
    if version.status != DocumentTemplateVersion.DRAFT:
        raise ValidationError("Only draft versions can be edited.")
    validate_design_document(design, width, height)
    version.design = design
    version.page_width_mm = width
    version.page_height_mm = height
    if background is not None:
        version.background = background
    if background_fit:
        version.background_fit = background_fit
    version.notes = notes
    version.save()
    return version


def submit_for_review(version: DocumentTemplateVersion, user):
    if version.status != DocumentTemplateVersion.DRAFT:
        raise ValidationError("Only draft versions can be submitted for review.")
    version.status = DocumentTemplateVersion.IN_REVIEW
    version.submitted_by = user
    version.submitted_at = timezone.now()
    version.save(update_fields=["status", "submitted_by", "submitted_at", "updated_at"])
    return version


def approve_version(version: DocumentTemplateVersion, user):
    if version.status != DocumentTemplateVersion.IN_REVIEW:
        raise ValidationError("Only versions in review can be approved.")
    version.status = DocumentTemplateVersion.APPROVED
    version.approved_by = user
    version.approved_at = timezone.now()
    version.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    return version


def activate_version(version: DocumentTemplateVersion, user):
    if version.status not in {DocumentTemplateVersion.APPROVED, DocumentTemplateVersion.ACTIVE}:
        raise ValidationError("Only an approved version can be activated.")
    with transaction.atomic():
        DocumentTemplateVersion.objects.filter(template=version.template, status=DocumentTemplateVersion.ACTIVE).exclude(pk=version.pk).update(status=DocumentTemplateVersion.ARCHIVED)
        if version.status != DocumentTemplateVersion.ACTIVE:
            version.status = DocumentTemplateVersion.ACTIVE
            version.activated_by = user
            version.activated_at = timezone.now()
            version.save(update_fields=["status", "activated_by", "activated_at", "updated_at"])
        template = version.template
        template.active_version_number = version.number
        template.is_active = True
        template.updated_by = user
        template.save(update_fields=["active_version_number", "is_active", "updated_by", "updated_at"])
    return version


def resolve_template_for_student(document_type: str, student) -> DocumentTemplate | None:
    class_group = getattr(getattr(student, "stream", None), "class_group", None)
    level_id = getattr(class_group, "level_id", None)
    qs = DocumentTemplate.objects.filter(document_type=document_type, is_active=True, active_version_number__isnull=False)
    candidates = [
        qs.filter(campus_id=student.campus_id, level_id=level_id, is_default=True),
        qs.filter(campus_id=student.campus_id, level__isnull=True, is_default=True),
        qs.filter(campus__isnull=True, level_id=level_id, is_default=True),
        qs.filter(campus__isnull=True, level__isnull=True, is_default=True),
    ]
    for candidate in candidates:
        template = candidate.order_by("-stage_id", "pk").first()
        if template and template.active_version:
            return template
    return None


def build_snapshot(student, term=None, *, reference="PREVIEW", verification_url="") -> dict:
    campus = student.campus
    organization = getattr(campus, "organization", None) if campus else OrganizationProfile.objects.first()
    class_group = getattr(getattr(student, "stream", None), "class_group", None)
    try:
        from apps.tenant.institutional.services import academic_summary, course_results
        summary = academic_summary(student, term)
        result_rows = course_results(student, term)
    except Exception:
        summary = {}
        result_rows = []
    results = []
    for row in result_rows:
        course = row.get("course")
        results.append({
            "subject": getattr(course, "name", str(course or "")),
            "percentage": _json_value(row.get("percentage")),
            "grade": _json_value(row.get("grade")),
            "remark": _json_value(row.get("remark")),
        })
    mean = summary.get("mean")
    mean_text = f"{mean}%" if mean not in (None, "") else ""
    return {
        "school": {
            "name": getattr(organization, "name", "") or "",
            "email": getattr(organization, "email", "") or "",
            "phone": getattr(organization, "phone", "") or "",
            "address": getattr(organization, "address", "") or "",
            "logo_name": getattr(getattr(organization, "logo", None), "name", "") or "",
        },
        "campus": {
            "name": getattr(campus, "name", "") or "",
            "code": getattr(campus, "code", "") or "",
            "email": getattr(campus, "email", "") or "",
            "phone": getattr(campus, "phone", "") or "",
            "address": getattr(campus, "address", "") or "",
            "logo_name": getattr(getattr(campus, "logo_override", None), "name", "") or "",
        },
        "student": {
            "full_name": student.get_full_name(),
            "first_name": student.first_name,
            "last_name": student.last_name,
            "student_id": student.student_id or "",
            "learner_id": getattr(student, "learner_id", "") or "",
            "email": student.email or "",
            "date_of_birth": student.date_of_birth.strftime("%d %b %Y") if student.date_of_birth else "",
            "class": getattr(class_group, "name", "") or "",
            "stream": getattr(getattr(student, "stream", None), "name", "") or "",
            "photo_name": getattr(getattr(student, "photo", None), "name", "") or "",
        },
        "academic": {
            "term": getattr(term, "name", "") if term else "",
            "year": getattr(getattr(term, "year", None), "name", "") if term else "",
            "mean": mean_text,
            "overall_grade": _json_value(summary.get("overall_grade")),
            "overall_remark": _json_value(summary.get("overall_remark")),
        },
        "document": {
            "reference": reference,
            "issue_date": timezone.localdate().strftime("%d %b %Y"),
            "verification_url": verification_url,
        },
        "results": results,
    }


def _lookup(snapshot: dict, binding: str):
    if binding == "school.logo":
        return snapshot.get("school", {}).get("logo_name", "")
    if binding == "campus.logo":
        return snapshot.get("campus", {}).get("logo_name", "")
    if binding == "student.photo":
        return snapshot.get("student", {}).get("photo_name", "")
    section, _, key = binding.partition(".")
    return snapshot.get(section, {}).get(key, "")


def _storage_image(field_file, fallback_name=""):
    if field_file and getattr(field_file, "name", ""):
        try:
            field_file.open("rb")
            return ImageReader(field_file)
        except Exception:
            return None
    if fallback_name:
        from django.core.files.storage import default_storage
        try:
            with default_storage.open(fallback_name, "rb") as handle:
                return ImageReader(io.BytesIO(handle.read()))
        except Exception:
            return None
    return None


def _draw_image(c, image, x, y, width, height, fit="contain"):
    if not image:
        c.saveState()
        c.setStrokeColor(colors.HexColor("#CBD5E1"))
        c.rect(x, y, width, height, stroke=1, fill=0)
        c.restoreState()
        return
    try:
        iw, ih = image.getSize()
        if fit == "stretch":
            dx, dy, dw, dh = x, y, width, height
        else:
            scale = max(width / iw, height / ih) if fit == "cover" else min(width / iw, height / ih)
            dw, dh = iw * scale, ih * scale
            dx, dy = x + (width - dw) / 2, y + (height - dh) / 2
        c.drawImage(image, dx, dy, width=dw, height=dh, mask="auto", preserveAspectRatio=False)
    except Exception:
        return


def _element_rect(element, page_height_pt):
    x = float(element.get("x", 0)) * mm
    top = float(element.get("y", 0)) * mm
    width = float(element.get("width", 1)) * mm
    height = float(element.get("height", 1)) * mm
    y = page_height_pt - top - height
    return x, y, width, height


def _color(value, fallback="#0F172A"):
    try:
        return colors.HexColor(value or fallback)
    except Exception:
        return colors.HexColor(fallback)


def _draw_text(c, element, value, page_height_pt):
    x, y, width, height = _element_rect(element, page_height_pt)
    font = element.get("fontFamily", "Helvetica")
    if element.get("bold") and font == "Helvetica":
        font = "Helvetica-Bold"
    elif element.get("bold") and font == "Times-Roman":
        font = "Times-Bold"
    elif element.get("bold") and font == "Courier":
        font = "Courier-Bold"
    align = {"left": TA_LEFT, "center": TA_CENTER, "right": TA_RIGHT}.get(element.get("align"), TA_LEFT)
    style = ParagraphStyle(
        name=f"ds-{element.get('id')}",
        fontName=font,
        fontSize=float(element.get("fontSize", 10)),
        leading=float(element.get("lineHeight", element.get("fontSize", 10) * 1.2)),
        textColor=_color(element.get("color")),
        alignment=align,
        spaceAfter=0,
        spaceBefore=0,
    )
    text = f"{element.get('prefix', '')}{value}{element.get('suffix', '')}"
    paragraph = Paragraph(escape(str(text)).replace("\n", "<br/>"), style)
    _, needed = paragraph.wrap(width, height)
    paragraph.drawOn(c, x, y + max(0, height - min(height, needed)))


def _draw_results_table(c, element, snapshot, page_height_pt):
    x, y, width, height = _element_rect(element, page_height_pt)
    rows = [["Subject / Course", "%", "Grade", "Remark"]]
    for row in snapshot.get("results", []):
        rows.append([row.get("subject", ""), row.get("percentage", "") or "—", row.get("grade", "") or "—", row.get("remark", "") or "—"])
    if len(rows) == 1:
        rows.append(["No results available", "—", "—", "—"])
    table = Table(rows, colWidths=[width * .44, width * .14, width * .14, width * .28], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _color(element.get("headerColor"), "#1E3A8A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), float(element.get("fontSize", 8))),
        ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    _, table_h = table.wrap(width, height)
    table.drawOn(c, x, y + max(0, height - table_h))


def render_version_pdf(version: DocumentTemplateVersion, student, term=None, *, snapshot=None, verification_url="") -> io.BytesIO:
    if snapshot is None:
        snapshot = build_snapshot(student, term, verification_url=verification_url)
    elif verification_url:
        snapshot = copy.deepcopy(snapshot)
        snapshot.setdefault("document", {})["verification_url"] = verification_url
    width_pt = float(version.page_width_mm) * mm
    height_pt = float(version.page_height_mm) * mm
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width_pt, height_pt), pageCompression=1)
    pages = (version.design or {}).get("pages", [])
    for page in pages:
        if version.background:
            background = _storage_image(version.background)
            _draw_image(c, background, 0, 0, width_pt, height_pt, fit=version.background_fit.lower())
        for element in page.get("elements", []):
            element_type = element.get("type")
            if element_type in {"text", "field"}:
                value = element.get("text", "") if element_type == "text" else _lookup(snapshot, element.get("binding", ""))
                _draw_text(c, element, value, height_pt)
            elif element_type == "image":
                x, y, width, height = _element_rect(element, height_pt)
                binding = element.get("binding", "")
                image = None
                if binding == "student.photo":
                    image = _storage_image(getattr(student, "photo", None), _lookup(snapshot, binding))
                elif binding == "campus.logo":
                    image = _storage_image(getattr(getattr(student, "campus", None), "logo_override", None), _lookup(snapshot, binding))
                elif binding == "school.logo":
                    org = getattr(getattr(student, "campus", None), "organization", None) or OrganizationProfile.objects.first()
                    image = _storage_image(getattr(org, "logo", None), _lookup(snapshot, binding))
                _draw_image(c, image, x, y, width, height, fit=element.get("fit", "contain"))
                if element.get("borderWidth"):
                    c.setStrokeColor(_color(element.get("borderColor"), "#CBD5E1"))
                    c.setLineWidth(float(element.get("borderWidth", .4)))
                    c.rect(x, y, width, height, stroke=1, fill=0)
            elif element_type == "qr":
                x, y, width, height = _element_rect(element, height_pt)
                value = _lookup(snapshot, element.get("binding", ""))
                if not value:
                    continue
                widget = QrCodeWidget(str(value))
                bounds = widget.getBounds()
                drawing = Drawing(width, height, transform=[width / (bounds[2]-bounds[0]), 0, 0, height / (bounds[3]-bounds[1]), 0, 0])
                drawing.add(widget)
                renderPDF.draw(drawing, c, x, y)
            elif element_type == "rectangle":
                x, y, width, height = _element_rect(element, height_pt)
                c.saveState()
                bg = element.get("backgroundColor")
                if bg and bg != "transparent":
                    c.setFillColor(_color(bg, "#FFFFFF"))
                c.setStrokeColor(_color(element.get("borderColor"), "#CBD5E1"))
                c.setLineWidth(float(element.get("borderWidth", .5)))
                c.rect(x, y, width, height, stroke=1 if float(element.get("borderWidth", .5)) else 0, fill=1 if bg and bg != "transparent" else 0)
                c.restoreState()
            elif element_type == "line":
                x, y, width, height = _element_rect(element, height_pt)
                c.saveState()
                c.setStrokeColor(_color(element.get("color"), "#334155"))
                c.setLineWidth(float(element.get("borderWidth", .5)))
                c.line(x, y + height, x + width, y)
                c.restoreState()
            elif element_type == "results_table":
                _draw_results_table(c, element, snapshot, height_pt)
        c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


def issue_document(template: DocumentTemplate, student, term, user, build_verify_url) -> IssuedDocument:
    version = template.active_version
    if not version:
        raise ValidationError("This template does not have an active approved version.")
    reference = f"{template.document_type[:8]}-{timezone.localdate():%Y%m%d}-{student.pk}-{secrets.token_hex(3).upper()}"
    with transaction.atomic():
        issued = IssuedDocument.objects.create(
            template=template,
            version=version,
            student=student,
            academic_term=term,
            reference=reference,
            data_snapshot={},
            issued_by=user,
        )
        verify_url = build_verify_url(issued.verification_token)
        issued.data_snapshot = build_snapshot(student, term, reference=reference, verification_url=verify_url)
        issued.save(update_fields=["data_snapshot"])
        pdf = render_version_pdf(version, student, term, snapshot=issued.data_snapshot, verification_url=verify_url)
        issued.pdf_file.save(f"{reference}.pdf", ContentFile(pdf.getvalue()), save=True)
    return issued
