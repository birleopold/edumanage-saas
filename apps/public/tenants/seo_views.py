import json
from xml.etree import ElementTree

from django.conf import settings
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET
from django_tenants.utils import get_public_schema_name


PUBLIC_INDEXABLE_PATHS = frozenset(
    {
        "/",
        "/features/",
        "/school-management-software/",
        "/pricing/",
        "/contact/",
        "/privacy/",
        "/terms/",
    }
)

MARKETING_PAGES = {
    "features": {
        "route_name": "marketing_features",
        "title": "School Management System Features | EduManage",
        "description": "Explore EduManage features for admissions, student records, attendance, fees, assessments, reports, communication, analytics and multi-campus school operations.",
        "eyebrow": "One connected school platform",
        "heading": "Everything a modern school needs to operate with confidence",
        "intro": "EduManage brings academic, administrative, financial and communication workflows into one secure cloud-based school management system.",
        "sections": [
            {
                "title": "Admissions and student records",
                "text": "Move applicants from online application to enrollment while maintaining reliable student profiles and campus records.",
                "bullets": ["Online applications", "Enrollment workflows", "Student and guardian records", "Document management"],
            },
            {
                "title": "Academics and assessment",
                "text": "Coordinate classes, timetables, coursework, attendance, assessments, examinations and report preparation.",
                "bullets": ["Timetables and attendance", "Coursework and quizzes", "Assessment score entry", "Exams and reports"],
            },
            {
                "title": "Fees and school finance",
                "text": "Give administrators a clear view of invoices, balances, payment evidence, reminders and finance reporting.",
                "bullets": ["Student invoices", "Payment recording", "Outstanding-fee tracking", "Finance exports and reports"],
            },
            {
                "title": "Communication and oversight",
                "text": "Keep staff, parents and students informed while giving school leaders the analytics and audit evidence they need.",
                "bullets": ["Announcements and messaging", "Parent portals", "Analytics dashboards", "Audit trails and permissions"],
            },
        ],
        "cta_title": "See how EduManage fits your school",
        "cta_text": "Start with the modules you need and expand as your school grows.",
    },
    "school_software": {
        "route_name": "marketing_school_software",
        "title": "Cloud School Management Software for Schools | EduManage",
        "description": "EduManage is cloud school management software for student information, attendance, fees, exams, reports, admissions and parent communication in one secure platform.",
        "eyebrow": "School management software",
        "heading": "Run daily school operations from one secure cloud platform",
        "intro": "Replace disconnected spreadsheets and isolated tools with a central system built for administrators, teachers, students and parents.",
        "sections": [
            {
                "title": "Designed for real school workflows",
                "text": "EduManage connects the work schools perform every day, from admitting a learner to recording attendance, collecting fees and publishing results.",
                "bullets": ["Single source of school data", "Role-based user portals", "Multi-campus support", "Mobile-friendly access"],
            },
            {
                "title": "Clearer decisions for school leaders",
                "text": "Dashboards, reports and operational alerts help leaders see what needs attention without waiting for manual summaries.",
                "bullets": ["Enrollment visibility", "Attendance monitoring", "Fee-balance oversight", "Academic performance reporting"],
            },
            {
                "title": "Secure access for every role",
                "text": "Each user sees the tools and records appropriate to their responsibilities, with tenant isolation and audit trails supporting accountability.",
                "bullets": ["Administrator controls", "Teacher workspaces", "Student self-service", "Parent access"],
            },
            {
                "title": "Built to grow beyond one school",
                "text": "The multi-tenant architecture supports independent school domains, subscriptions and data isolation for institutions of different sizes.",
                "bullets": ["Independent school workspaces", "Custom and subdomain routing", "Plan-based features", "Scalable PostgreSQL tenancy"],
            },
        ],
        "cta_title": "Modernise your school operations",
        "cta_text": "Talk to EduManage about your institution, campuses and priority workflows.",
    },
    "pricing": {
        "route_name": "marketing_pricing",
        "title": "EduManage Pricing and School Plans",
        "description": "Request EduManage pricing for your school. Plans can be matched to enrollment size, campuses, modules, implementation and support requirements.",
        "eyebrow": "Flexible school plans",
        "heading": "Pricing aligned with your school’s size and operational needs",
        "intro": "Schools differ in enrollment, campuses, reporting needs and implementation support. EduManage pricing is prepared around the modules and capacity your institution requires.",
        "sections": [
            {
                "title": "Start with essential operations",
                "text": "Create a practical foundation for student records, attendance, academics and communication without paying for unnecessary complexity.",
                "bullets": ["Core school records", "User portals", "Attendance and academics", "Standard support"],
            },
            {
                "title": "Add advanced modules",
                "text": "Extend the system with finance, admissions, analytics, transport, library, inventory, hostels, HR and other operational modules.",
                "bullets": ["Module-based expansion", "Multi-campus operations", "Advanced reports", "Integrations"],
            },
            {
                "title": "Implementation support",
                "text": "Migration, configuration, training and rollout support can be scoped according to the condition of your existing data and processes.",
                "bullets": ["Initial configuration", "Data preparation", "Administrator training", "Go-live support"],
            },
        ],
        "cta_title": "Request a tailored quotation",
        "cta_text": "Share your enrollment, campuses and required modules for an appropriate plan recommendation.",
    },
    "contact": {
        "route_name": "marketing_contact",
        "title": "Contact EduManage | School Management Software",
        "description": "Contact EduManage for school management software demonstrations, pricing, onboarding, technical questions and institutional partnerships.",
        "eyebrow": "Contact EduManage",
        "heading": "Let’s discuss what your school needs to manage better",
        "intro": "Tell us about your institution, enrollment, campuses and the processes you want to improve. The EduManage team can guide the next step.",
        "sections": [
            {
                "title": "Product demonstrations",
                "text": "Review the workflows that matter to your school and see how the administrator, teacher, student and parent portals work together.",
                "bullets": ["Guided product tour", "Workflow discussion", "Module recommendations", "Implementation questions"],
            },
            {
                "title": "Onboarding and support",
                "text": "Get help with school setup, account access, domain routing, data preparation and operational rollout.",
                "bullets": ["School configuration", "User onboarding", "Technical support", "Deployment guidance"],
            },
        ],
        "cta_title": "Email the EduManage team",
        "cta_text": "Send your school name, location, approximate enrollment and priority modules.",
    },
    "privacy": {
        "route_name": "marketing_privacy",
        "title": "Privacy Policy | EduManage",
        "description": "Read how EduManage approaches personal information, school records, account security, service operations and privacy responsibilities.",
        "eyebrow": "Privacy",
        "heading": "Privacy and responsible handling of school information",
        "intro": "EduManage is designed to help institutions manage sensitive education records responsibly. Each school remains responsible for lawful collection and use of its records.",
        "sections": [
            {
                "title": "Information processed",
                "text": "Depending on enabled modules, schools may process account details, student and guardian records, attendance, academic, finance and communication information.",
                "bullets": ["Account and role information", "Institutional records", "Operational activity logs", "Support communications"],
            },
            {
                "title": "Security and access",
                "text": "Role-based access, tenant separation, HTTPS, secure cookies and audit records support confidentiality and accountability.",
                "bullets": ["Role-based permissions", "Tenant data isolation", "Security logging", "Controlled administrative access"],
            },
            {
                "title": "Retention and requests",
                "text": "Retention, correction, export and deletion requirements depend on institutional policy and applicable law. Requests should normally begin with the relevant school administrator.",
                "bullets": ["Institution-led record management", "Support-assisted exports", "Incident response", "Policy review"],
            },
        ],
        "cta_title": "Privacy questions",
        "cta_text": "Contact EduManage support or your school administrator for questions about a specific record.",
    },
    "terms": {
        "route_name": "marketing_terms",
        "title": "Terms of Service | EduManage",
        "description": "Review the general terms governing access to EduManage, authorised use, school responsibilities, availability, subscriptions and support.",
        "eyebrow": "Terms of service",
        "heading": "Terms for responsible use of the EduManage platform",
        "intro": "These general terms describe the expected use of EduManage. A school’s signed agreement, quotation or service schedule may include additional commercial terms.",
        "sections": [
            {
                "title": "Authorised access",
                "text": "Users must access only the school workspace, roles and records they are authorised to use and must protect their account credentials.",
                "bullets": ["Use assigned accounts", "Protect passwords", "Respect role permissions", "Report suspected misuse"],
            },
            {
                "title": "Institution responsibilities",
                "text": "Schools are responsible for the accuracy and lawful collection of the information entered by their authorised users.",
                "bullets": ["Maintain accurate records", "Manage user access", "Obtain required permissions", "Follow applicable policies and laws"],
            },
            {
                "title": "Service and subscriptions",
                "text": "Access may depend on the agreed plan, payment state, supported configuration and acceptable use of the service.",
                "bullets": ["Plan-based access", "Scheduled maintenance", "Support cooperation", "Suspension for serious misuse"],
            },
        ],
        "cta_title": "Questions about service terms",
        "cta_text": "Contact the EduManage team before onboarding when your institution requires specific contractual terms.",
    },
}

HOME_PAGE = {
    "route_name": "marketing_home",
    "title": "EduManage | Cloud School Management Software",
    "description": "EduManage is secure cloud school management software for admissions, student records, attendance, fees, exams, reports, analytics and parent communication.",
}


def _is_public_schema():
    return getattr(connection, "schema_name", get_public_schema_name()) == get_public_schema_name()


def _canonical_origin(request):
    configured = str(getattr(settings, "SEO_CANONICAL_ORIGIN", "") or "").strip().rstrip("/")
    if configured:
        return configured
    return f"{'https' if request.is_secure() else 'http'}://{request.get_host()}"


def _static_absolute_url(request, path):
    if str(path).startswith(("http://", "https://")):
        return str(path)
    origin = _canonical_origin(request)
    return f"{origin}/{str(path).lstrip('/')}"


def _structured_data(request, page, canonical_url):
    origin = _canonical_origin(request)
    logo_url = _static_absolute_url(
        request,
        getattr(settings, "SEO_LOGO_URL", "") or f"/{settings.STATIC_URL.strip('/')}/img/pwa-icon.svg",
    )
    organization_id = f"{origin}/#organization"
    website_id = f"{origin}/#website"
    graph = [
        {
            "@type": "Organization",
            "@id": organization_id,
            "name": getattr(settings, "SEO_ORGANIZATION_NAME", "EduManage"),
            "url": origin,
            "logo": {"@type": "ImageObject", "url": logo_url},
            "email": getattr(settings, "SEO_CONTACT_EMAIL", ""),
        },
        {
            "@type": "WebSite",
            "@id": website_id,
            "url": origin,
            "name": getattr(settings, "SEO_SITE_NAME", "EduManage"),
            "alternateName": getattr(settings, "SEO_SITE_ALTERNATE_NAME", "EduManage School Management System"),
            "publisher": {"@id": organization_id},
            "inLanguage": "en",
        },
        {
            "@type": "WebApplication",
            "@id": f"{origin}/#software",
            "name": "EduManage",
            "url": origin,
            "description": HOME_PAGE["description"],
            "applicationCategory": "EducationalApplication",
            "operatingSystem": "Web",
            "browserRequirements": "Requires a modern web browser and internet connection",
            "publisher": {"@id": organization_id},
            "featureList": [
                "Admissions management",
                "Student information management",
                "Attendance management",
                "School fees and invoicing",
                "Assessments and examinations",
                "Reports and analytics",
                "Parent, student and teacher portals",
                "Multi-campus and multi-tenant operations",
            ],
        },
    ]
    if page["route_name"] != "marketing_home":
        graph.append(
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "name": "Home",
                        "item": origin + reverse("marketing_home"),
                    },
                    {
                        "@type": "ListItem",
                        "position": 2,
                        "name": page["heading"],
                        "item": canonical_url,
                    },
                ],
            }
        )
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)


def _seo_context(request, page):
    origin = _canonical_origin(request)
    canonical_url = origin + request.path
    image_url = _static_absolute_url(
        request,
        getattr(settings, "SEO_DEFAULT_IMAGE_URL", "") or f"/{settings.STATIC_URL.strip('/')}/img/pwa-icon.svg",
    )
    return {
        "site_name": getattr(settings, "SEO_SITE_NAME", "EduManage"),
        "title": page["title"],
        "description": page["description"],
        "canonical_url": canonical_url,
        "image_url": image_url,
        "locale": getattr(settings, "SEO_LOCALE", "en_UG"),
        "google_verification": getattr(settings, "SEO_GOOGLE_SITE_VERIFICATION", ""),
        "bing_verification": getattr(settings, "SEO_BING_SITE_VERIFICATION", ""),
        "google_analytics_id": getattr(settings, "SEO_GOOGLE_ANALYTICS_ID", ""),
        "structured_data": _structured_data(request, page, canonical_url),
    }


@require_GET
def marketing_home(request):
    context = {
        "seo": _seo_context(request, HOME_PAGE),
        "contact_email": getattr(settings, "SEO_CONTACT_EMAIL", "admin@leosoftug.com"),
    }
    return render(request, "public/marketing_home.html", context)


@require_GET
def marketing_page(request, page_key):
    page = MARKETING_PAGES[page_key]
    context = {
        "page": page,
        "seo": _seo_context(request, page),
        "contact_email": getattr(settings, "SEO_CONTACT_EMAIL", "admin@leosoftug.com"),
    }
    return render(request, "public/marketing_page.html", context)


@require_GET
def robots_txt(request):
    if not _is_public_schema():
        body = "User-agent: *\nDisallow: /\n"
    else:
        origin = _canonical_origin(request)
        body = "\n".join(
            [
                "User-agent: *",
                "Allow: /",
                "Disallow: /dj-admin/",
                "Disallow: /health/",
                "Disallow: /api/",
                "Disallow: /pwa/",
                "Disallow: /messages/",
                "Disallow: /notifications/",
                "Disallow: /service-worker.js",
                f"Sitemap: {origin}/sitemap.xml",
                "",
            ]
        )
    response = HttpResponse(body, content_type="text/plain; charset=utf-8")
    response["Cache-Control"] = "public, max-age=3600"
    return response


@require_GET
def sitemap_xml(request):
    urlset = ElementTree.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    if _is_public_schema():
        origin = _canonical_origin(request)
        pages = [HOME_PAGE, *MARKETING_PAGES.values()]
        for page in pages:
            url = ElementTree.SubElement(urlset, "url")
            location = ElementTree.SubElement(url, "loc")
            location.text = origin + reverse(page["route_name"])
    xml = ElementTree.tostring(urlset, encoding="utf-8", xml_declaration=True)
    response = HttpResponse(xml, content_type="application/xml; charset=utf-8")
    response["Cache-Control"] = "public, max-age=3600"
    return response
