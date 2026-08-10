# EduManage Design Studio

Design Studio is the tenant-scoped visual document production engine for official school documents.

## Supported document families

- Student ID cards
- End-of-term report cards
- Academic transcripts
- Leavers certificates
- Admission letters
- Examination permits
- General certificates and custom documents

## Design workflow

1. Create a template and choose its campus/stage/level scope.
2. Open the visual designer.
3. Start from the EduManage default layout or upload JPG/PNG artwork as a background.
4. Add static text, shapes, QR codes, results tables and safe data-bound fields.
5. Preview with a real learner and academic period.
6. Submit the draft for approval.
7. An administrator or principal approves and activates the version.
8. Issue official documents from the active version.

Approved/active/archived version payloads are immutable. Editing an official design creates a new draft version instead of altering historical versions.

## Issued document integrity

Official issuance stores:

- the exact active template version;
- a JSON data snapshot;
- the generated PDF file;
- a unique reference and verification token;
- issuing user and timestamp.

The QR code resolves to a tenant verification page. Revoked documents remain auditable and verify as invalid.

## Safe data bindings

The browser never evaluates arbitrary Django/Python expressions. Bindings are selected from a server-maintained allow-list such as `student.full_name`, `school.name`, `academic.term` and `document.verification_url`. This prevents a visual template from becoming a path to unrelated tenant data.

## Rendering

The editor stores layouts as structured JSON using millimetre coordinates. ReportLab renders the approved version on the server. Academic calculations remain in the existing assessments/institutional result services; Design Studio controls presentation only.

## Background artwork

Schools can upload professional JPG/PNG artwork prepared in Publisher, Canva, Photoshop, CorelDRAW or similar software. The artwork is stored as the version background and cannot be modified after approval. Dynamic fields can then be positioned over the artwork.

## Deployment

After merging:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

For tenant production deployments:

```bash
DJANGO_SETTINGS_MODULE=config.settings.tenants python manage.py migrate_schemas --tenant --noinput
DJANGO_SETTINGS_MODULE=config.settings.tenants python manage.py collectstatic --noinput
```
