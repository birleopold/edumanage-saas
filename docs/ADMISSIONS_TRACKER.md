# Parent Self-Service Admissions Tracker

The public admissions tracker lets applicants and parents check application progress without needing a portal account.

## Where To Find It

- Public tracker: `/apply/track/`
- Public application form: `/apply/`
- Landing page: Track application button
- Submission success page: Track application button with the reference prefilled

## Lookup Rules

Parents enter the application reference. They can also enter the phone or email used during application. When contact is provided, the tracker only shows an application if the reference and contact match.

## Tracker Sections

The tracker shows:

- Application timeline
- Required document checklist
- Uploaded supporting documents
- Interview, admission test or parent meeting schedule
- Current admission decision
- Payment instructions, admission payment requests and admission invoice balance

## Data Sources

The page uses existing admissions records:

- `Applicant`
- `ApplicantDocument`
- `AdmissionAppointment`
- `ApplicantPayment`
- linked admission invoice
- linked converted student profile

## Operational Notes

- No new database table or migration is required.
- Parents only see applications that match the entered reference and optional contact.
- The required document checklist is a school-friendly default list. More formal per-class requirements can be added later through admissions form templates.
