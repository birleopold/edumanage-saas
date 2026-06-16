# EduManage SaaS - School Management System

EduManage SaaS is a Django-based school management system for handling school administration, academic records, finance, communication, and reporting. The project is designed to support a SaaS/multi-tenant deployment model using `django-tenants`, while still allowing simple local development with SQLite.

## Main Features

### Core Modules

- **Multi-tenancy**: Tenant-aware setup using PostgreSQL schemas through `django-tenants`.
- **User management**: Role-based access for admins, teachers, students, and parents.
- **Academic management**: Academic years, terms, levels, programs, streams, courses, and enrollment.
- **Student management**: Student profiles, academic records, and parent links.
- **Teacher management**: Teacher profiles, course assignments, attendance, and grading workflows.
- **Admissions**: Application processing and student onboarding.
- **Attendance**: Session-based attendance and roll-call tracking.
- **Assessments and exams**: Assessment capture, grading, exam papers, and result management.
- **Finance**: Fees, invoices, payments, reminders, and receipts.
- **Library**: Book catalog, inventory, and loan management.
- **Timetable**: Period scheduling, rooms, and class timetables.
- **Transport**: Route management and student transport assignments.
- **Hostel**: Accommodation and bed allocation.
- **Discipline**: Incident recording and disciplinary actions.
- **Inventory**: Asset tracking and assignments.
- **Documents**: File sharing with audience targeting.
- **Announcements**: School communication and notices.
- **Reports**: Analytics and exports.

### Branding and Customization

- Organization-level branding.
- Campus-level logo and branding overrides.
- Custom primary and secondary colors.

## Tech Stack

- **Backend**: Django 4.2 LTS
- **Tenancy**: django-tenants
- **Database**: SQLite for simple local development, PostgreSQL for tenant/SaaS deployment
- **Frontend**: Django templates, Tailwind CSS, Alpine.js, Phosphor Icons
- **API**: Django REST Framework
- **Static files**: WhiteNoise
- **Documents/Reports**: Pillow and ReportLab

## Project Structure

```text
edumanage-saas/
├── apps/
│   ├── public/          # Public-schema tenant/domain models and public views
│   └── tenant/          # Tenant-specific school modules
├── config/
│   ├── settings/
│   │   ├── base.py      # Common settings
│   │   ├── local.py     # Local development settings
│   │   ├── tenants.py   # django-tenants/PostgreSQL settings
│   │   └── prod.py      # Production settings
│   ├── urls.py
│   ├── public_urls.py
│   ├── asgi.py
│   └── wsgi.py
├── templates/
├── staticfiles/
├── media/
├── manage.py
├── requirements.txt
└── .env.example
```

## Requirements

- Python 3.10+
- pip and virtualenv
- PostgreSQL 13+ for tenant/SaaS deployment

## Quick Start: Local Development

The default `manage.py` uses `config.settings.local`, which is the simplest setup for local development.

1. **Clone the repository**

```bash
git clone https://github.com/birleopold/edumanage-saas.git
cd edumanage-saas
```

2. **Create and activate a virtual environment**

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Create your environment file**

```bash
cp .env.example .env
```

Update `.env` with your local values.

5. **Run migrations**

```bash
python manage.py migrate
```

6. **Create a superuser**

```bash
python manage.py createsuperuser
```

7. **Run the development server**

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000`.

## Tenant/SaaS Setup with PostgreSQL

Use this mode when testing or deploying the multi-tenant architecture.

1. Configure PostgreSQL variables in `.env`:

```env
POSTGRES_DB=edumanage_saas
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
```

2. Use the tenant settings module:

```bash
export DJANGO_SETTINGS_MODULE=config.settings.tenants
```

On Windows PowerShell:

```powershell
$env:DJANGO_SETTINGS_MODULE="config.settings.tenants"
```

3. Run schema migrations:

```bash
python manage.py migrate_schemas --shared
python manage.py migrate_schemas
```

4. Create the public tenant/domain records through Django admin or a management command.

## Production Notes

Production uses `config.settings.prod`, which imports the tenant settings and adds secure cookie/proxy settings.

Before deployment, configure at least:

```env
DJANGO_SECRET_KEY=replace-this-with-a-strong-secret
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DJANGO_TIME_ZONE=Africa/Kampala
POSTGRES_DB=edumanage_saas
POSTGRES_USER=edumanage_user
POSTGRES_PASSWORD=strong-password
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
```

Recommended production setup:

- Gunicorn or uWSGI behind Nginx.
- PostgreSQL database backups.
- HTTPS/SSL.
- Proper `ALLOWED_HOSTS`.
- Secure media file storage.
- Log rotation and error monitoring.
- Separate environment variables for secrets.

## Useful Commands

```bash
# Run Django checks
python manage.py check

# Create migrations
python manage.py makemigrations

# Apply local migrations
python manage.py migrate

# Apply tenant migrations
DJANGO_SETTINGS_MODULE=config.settings.tenants python manage.py migrate_schemas

# Collect static files
python manage.py collectstatic

# Run tests
python manage.py test
```

## User Roles

- **Admin**: Full school administration and organization setup.
- **Teacher**: Course management, attendance, grading, and class operations.
- **Student**: Schedules, grades, assignments, and academic information.
- **Parent**: Student progress, attendance, invoices, and notices.

## API

API routes are mounted under:

```text
/api/v1/
```

The default REST framework permissions require authenticated users.

## Environment Variables

See `.env.example` for the supported configuration values.

## Contributing

1. Create a feature branch.
2. Keep changes focused and small.
3. Run checks before committing.
4. Open a pull request with a clear description of the change.

## License

This project is proprietary software. All rights reserved.

## Changelog

### Version 1.0.0

- Initial school management modules.
- Multi-tenant architecture foundation.
- Role-based access control.
- Tailwind-based portal UI.
- Date format placeholders across forms.
- Logo upload and branding support.
