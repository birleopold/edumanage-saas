# EduManage SaaS - UI Architecture & Design Guidelines

This document outlines the UI/UX architecture implemented across the EduManage SaaS platform to ensure consistency, simplicity, and user-friendliness.

## 1. Core Philosophy

- **Simplicity First:** Dashboards and forms must not overwhelm the user. Use progressive disclosure.
- **Role-Based Clarity:** Each user (Admin, Teacher, Student, Parent) sees only what they need, organized logically.
- **Consistent Visual Language:** Unified colors, typography, spacing, and icons across all portals.

## 2. Technology Stack

- **Framework:** Django Templates
- **CSS Framework:** Tailwind CSS (currently via CDN for rapid deployment, production should use PostCSS/Tailwind CLI).
- **Icons:** Phosphor Icons (clean, modern, consistent stroke weights).
- **Custom CSS:** Minimal custom CSS (`static/css/campus-ui.css`), mostly for scrollbar hiding and minor overrides.

## 3. Base Layouts (`base.html`)

We have distinct base templates for each role, sharing a common structure:

- `templates/portals/admin/base.html`
- `templates/portals/teacher/base.html`
- `templates/portals/student/base.html`
- `templates/portals/parent/base.html`

### Structural Elements:
- **Sidebar (Left):** Collapsible on mobile. Contains categorized navigation links grouped by functional area (e.g., "People", "Academics", "Operations").
- **Header (Top):** Contains context switchers (like Campus selectors), global search (placeholder), notifications, and user profile/logout.
- **Main Content Area:** A scrollable region with breadcrumbs, page titles, action buttons, and the main content block.

## 4. Navigation Design

Navigation is grouped logically rather than presented as a flat list:
- **Active States:** Highlighted with primary color backgrounds (`bg-primary-50 text-primary-700`).
- **Icons:** Every link has a descriptive Phosphor icon.
- **Typography:** Section headers use uppercase, tracking-wider, small text (`text-xs font-semibold text-gray-500 uppercase`).

## 5. Dashboards (`home.html`)

Dashboards have been transformed from basic link lists to "Mission Control" centers:
- **Welcome Banner:** Personalized greeting and context summary (e.g., current term, selected campus).
- **Quick Actions:** High-priority tasks represented as large, clickable cards with prominent icons (e.g., "Add Student", "Take Attendance").
- **KPI Widgets / Overviews:** Important metrics displayed in tables or cards.

## 6. Shared Components

To maintain consistency in future development, use these reusable components located in `templates/components/`:

### 6.1 UI Table (`ui_table.html`)
Provides a consistent, responsive table layout with hover states.
```django
{% include "components/ui_table.html" with headers=table_headers has_data=data %}
    {% block table_body %}
        <!-- loop rows here -->
    {% endblock %}
```

### 6.2 UI Form (`ui_form.html`)
Provides a consistent layout for Django forms, including error handling.
```django
{% include "components/ui_form.html" %}
    {% block form_method %}post{% endblock %}
    {% block grid_cols %}sm:grid-cols-2{% endblock %}
    {% block form_actions %}
        <!-- Custom buttons here -->
    {% endblock %}
```

## 7. Color Palette (Tailwind Configuration)

The primary color palette is centrally defined in the Tailwind config script within the `base.html` files.

- **Primary Colors:** Ranging from `primary-50` (very light background) to `primary-900` (deep text/headers).
- **Status Colors:**
  - Success/Active: Green (`text-green-600`, `bg-green-100`)
  - Warning/Pending: Yellow (`text-yellow-600`, `bg-yellow-100`)
  - Error/Danger: Red (`text-red-600`, `bg-red-100`)
  - Info: Blue (`text-blue-600`, `bg-blue-100`)

## 8. Adding New Views

When creating a new view (e.g., `admin_new_feature.html`):
1. **Extend** the appropriate base: `{% extends 'portals/admin/base.html' %}`
2. **Set Titles:** `{% block title %}Page Title{% endblock %}` and `{% block page_title %}Page Title{% endblock %}`
3. **Add Actions:** Use `{% block header_actions %}` for top-right buttons.
4. **Use Components:** Utilize `ui_table.html` or `ui_form.html` for standard data presentation/entry.
5. **Update Base:** Don't forget to add a link to your new view in the corresponding `base.html` sidebar, placing it in the correct category.
