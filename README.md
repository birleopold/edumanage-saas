# EduManage SaaS - School Management System

A comprehensive multi-tenant school management system built with Django, designed to handle all aspects of educational institution administration.

## Features

### Core Modules
- **Multi-Tenancy**: Isolated data per organization with campus-level management
- **User Management**: Role-based access control (Admin, Teacher, Student, Parent)
- **Academic Management**: Years, terms, levels, programs, streams, courses
- **Student Management**: Profiles, enrollment, academic records
- **Teacher Management**: Profiles, course assignments, attendance tracking
- **Admissions**: Application processing and student onboarding
- **Attendance**: Session-based tracking with roll call interface
- **Assessments & Exams**: Grading, exam papers, and result management
- **Finance**: Fee management, invoicing, and payment tracking
- **Library**: Book catalog, inventory, and loan management
- **Timetable**: Period scheduling and room management
- **Transport**: Route management and student assignments
- **Hostel**: Accommodation and bed allocation
- **Discipline**: Incident tracking and action management
- **Inventory**: Asset management and assignments
- **Documents**: File management with audience targeting
- **Announcements**: Communication system
- **Reports**: Analytics and data export

### Branding & Customization
- Organization and campus-level logo uploads
- Custom color schemes (primary/secondary)
- Two-level branding system with campus overrides

## Tech Stack

- **Backend**: Django 5.x with django-tenants
- **Database**: PostgreSQL (multi-tenant schema isolation)
- **Frontend**: Tailwind CSS, Alpine.js, Phosphor Icons
- **Storage**: Django FileField with tenant-aware uploads
- **API**: Django REST Framework

## Installation

### Prerequisites
- Python 3.10+
- PostgreSQL 13+
- pip and virtualenv

### Setup

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd edumanage_saas
```

2. **Create virtual environment**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
Create a `.env` file in the root directory:
```env
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_TIME_ZONE=UTC

# Database
DATABASE_URL=postgres://user:password@localhost:5432/edumanage_db
```

5. **Run migrations**
```bash
python manage.py migrate_schemas --shared
python manage.py migrate_schemas
```

6. **Create a superuser**
```bash
python manage.py createsuperuser
```

7. **Run the development server**
```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000` to access the application.

## Project Structure

```
edumanage_saas/
├── apps/
│   ├── public/          # Public schema apps
│   └── tenant/          # Tenant-specific apps
│       ├── academics/
│       ├── admissions/
│       ├── announcements/
│       ├── assessments/
│       ├── attendance/
│       ├── discipline/
│       ├── documents/
│       ├── exams/
│       ├── finance/
│       ├── hostels/
│       ├── hr/
│       ├── inventory/
│       ├── library/
│       ├── orgsettings/
│       ├── parents/
│       ├── portals/
│       ├── students/
│       ├── teachers/
│       ├── timetable/
│       ├── transport/
│       └── users/
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   └── wsgi.py
├── templates/
│   ├── components/
│   └── portals/
│       ├── admin/
│       ├── teacher/
│       ├── student/
│       └── parent/
├── staticfiles/
├── media/
├── manage.py
└── requirements.txt
```

## Usage

### Creating a New Tenant

1. Access Django admin at `/dj-admin/`
2. Create a new tenant organization
3. Configure organization settings and branding
4. Add campuses as needed
5. Set up academic structure (years, terms, levels, programs)

### User Roles

- **Admin**: Full system access, organization management
- **Teacher**: Course management, attendance, grading
- **Student**: View schedules, grades, assignments
- **Parent**: Monitor student progress and attendance

## Development

### Running Tests
```bash
python manage.py test
```

### Creating Migrations
```bash
python manage.py makemigrations
python manage.py migrate_schemas
```

### Collecting Static Files
```bash
python manage.py collectstatic
```

## Deployment

For production deployment:

1. Set `DJANGO_DEBUG=False`
2. Configure proper `ALLOWED_HOSTS`
3. Use a production-grade database (PostgreSQL)
4. Set up proper media file storage (S3, etc.)
5. Configure HTTPS/SSL
6. Set up proper logging
7. Use a production WSGI server (Gunicorn, uWSGI)
8. Configure static file serving (Nginx, CDN)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is proprietary software. All rights reserved.

## Support

For support and questions, please contact the development team.

## Changelog

### Version 1.0.0 (Current)
- Initial release with core modules
- Multi-tenant architecture
- Role-based access control
- Comprehensive school management features
- Modern UI with Tailwind CSS
- Date format placeholders across all forms
- Logo upload and branding system
