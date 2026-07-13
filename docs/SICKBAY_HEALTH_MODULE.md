# Sickbay & Student Health

EduManage now includes an admin sickbay module for schools with a nurse, doctor or first-aid room.

## Where To Find It

- Admin dashboard: `/admin/sickbay/`
- Visit log: `/admin/sickbay/visits/`
- Medical profiles: `/admin/sickbay/profiles/`
- Parent portal: `/parent/sickbay/`
- Student portal: `/student/sickbay/`
- Admin sidebar: Sickbay
- Admin command center: Sickbay & Health card

## What It Captures

Medical profile per student:

- Blood group
- Allergies
- Chronic conditions
- Current medication
- Emergency contact
- Preferred clinic or doctor
- Health notes

Sickbay visit records:

- Student and visit time
- Complaint and symptoms
- Severity
- Temperature
- Nurse or doctor name
- Treatment given
- Medicine and dosage
- Parent notification status and method
- Outcome, such as returned to class, sent home, referred or emergency escalation
- Follow-up requirement and notes

## Current Scope

The first version lets admins and campus admins record sickbay visits and medical profiles. Parents can view clinic visits and medical alerts for their linked children only. Students can view their own clinic visits and medical profile alerts from the student portal.

When staff mark a visit as parent-notified, linked parent portal accounts receive an in-app notification pointing to the parent sickbay page. A dedicated nurse or medical staff role can be added later if schools want sickbay staff to access only health records.

## Operational Notes

- This is a normal Django app and migration.
- No Node, npm, CDN or frontend build step is required.
- Health alerts are surfaced from allergies, chronic conditions and current medication fields.
