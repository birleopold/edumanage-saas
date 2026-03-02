# UI Components Guide - EduManage SaaS

Complete reference for all reusable UI components created for the EduManage platform.

---

## 📚 Component Library

### 1. **Form Component** (`ui_form.html`)

**Purpose:** Standardized form rendering with consistent styling, error handling, and field validation.

**Features:**
- Automatic field styling with Tailwind CSS
- 2px visible borders (gray-300)
- Bold labels for better visibility
- Error highlighting with red borders/backgrounds
- Support for all field types (text, checkbox, select, textarea)
- Integrated with `django-widget-tweaks`

**Usage:**
```django
{% load widget_tweaks %}
{% include "components/ui_form.html" %}
```

**Automatic Styling:**
- Text inputs: 2px border, rounded-lg, hover states
- Labels: Bold, gray-700
- Errors: Red background, red border, icon indicators
- Buttons: Primary gradient with hover effects

---

### 2. **Table Component** (`ui_table.html`)

**Purpose:** Consistent table styling across all list views.

**Features:**
- Responsive design with horizontal scroll
- Hover effects on rows
- Bold uppercase headers
- Proper spacing and borders
- Empty state handling

**Usage:**
```django
{% include "components/ui_table.html" %}
```

**Styling:**
- Header: Bold, uppercase, gray-500 text
- Rows: Hover bg-gray-50 transition
- Borders: Gray-200 dividers
- Padding: px-6 py-4 for cells

---

### 3. **Toast Notifications** (`ui_toast.html`)

**Purpose:** User feedback for actions (success, error, warning, info).

**Features:**
- Auto-dismiss after 5 seconds
- Slide-in animation from right
- Color-coded by message type
- Manual close button
- Stacks multiple messages

**Usage:**
```django
{% include "components/ui_toast.html" %}
```

**Message Types:**
- `success` → Green border, check icon
- `error/danger` → Red border, error icon
- `warning` → Yellow border, warning icon
- `info` → Blue border, info icon

**Location:** Fixed top-right corner, z-50

---

### 4. **Breadcrumb Navigation** (`ui_breadcrumb.html`)

**Purpose:** Show current page location in site hierarchy.

**Features:**
- Home icon for first item
- Chevron separators
- Active vs inactive states
- Responsive text sizing

**Usage:**
```django
{% include "components/ui_breadcrumb.html" with items=breadcrumb_items %}
```

**Data Format:**
```python
breadcrumb_items = [
    {'label': 'Home', 'url': '/admin/home/'},
    {'label': 'Students', 'url': '/admin/students/'},
    {'label': 'John Doe'}  # Current page (no URL)
]
```

---

### 5. **Pagination** (`ui_pagination.html`)

**Purpose:** Navigate through paginated list views.

**Features:**
- Shows current page, total pages
- Previous/Next buttons
- Direct page number links
- Mobile-responsive (simplified on mobile)
- Disabled state for unavailable navigation

**Usage:**
```django
{% include "components/ui_pagination.html" with page_obj=page_obj %}
```

**Requirements:**
- Django Paginator with `page_obj` in context
- Displays: "Showing X to Y of Z results"

---

### 6. **Search & Filter Bar** (`ui_search_filter.html`)

**Purpose:** Search and filter functionality for list views.

**Features:**
- Search input with icon
- Optional filter panel (toggle)
- Export button option
- Create/Add new button
- Responsive layout

**Usage:**
```django
{% include "components/ui_search_filter.html" with search_placeholder="Search students..." show_export=True show_filters=True create_url="/students/add/" create_text="Add Student" %}
```

**Parameters:**
- `search_placeholder` - Placeholder text for search
- `show_export` - Show/hide export button
- `show_filters` - Show/hide filters toggle
- `create_url` - URL for create button
- `create_text` - Text for create button

**Custom Filters:**
```django
{% block filters %}
  <select name="status" class="...">
    <option value="">All Status</option>
    <option value="active">Active</option>
  </select>
{% endblock %}
```

---

### 7. **Empty State** (`ui_empty_state.html`)

**Purpose:** Display when no data is available.

**Features:**
- Icon, title, description
- Optional action button
- Centered layout
- Professional appearance

**Usage:**
```django
{% include "components/ui_empty_state.html" with icon="users" title="No students found" description="Get started by adding your first student" action_url="/students/add/" action_text="Add Student" %}
```

**Parameters:**
- `icon` - Phosphor icon name (default: 'folder-open')
- `title` - Main heading text
- `description` - Optional explanatory text
- `action_url` - Optional button URL
- `action_text` - Button text (default: "Add New")

---

### 8. **Stat Card** (`ui_stat_card.html`)

**Purpose:** Display key metrics and statistics.

**Features:**
- Icon with colored background
- Large number display
- Trend indicators (up/down/neutral)
- Optional link to details
- Hover shadow effect

**Usage:**
```django
{% include "components/ui_stat_card.html" with title="Total Students" value="1,234" icon="users" color="blue" change="+12.5%" trend="up" link_url="/students/" link_text="View all" %}
```

**Parameters:**
- `title` - Card title (e.g., "Total Students")
- `value` - Main statistic value
- `icon` - Phosphor icon name
- `color` - Color theme (blue, green, purple, red, yellow, indigo)
- `change` - Optional change indicator (e.g., "+12.5%")
- `trend` - Trend direction ("up", "down", or neutral)
- `change_label` - Optional label (default: "vs last month")
- `link_url` - Optional link URL
- `link_text` - Link text (default: "View details")

---

### 9. **Loading Spinner** (`ui_loading.html`)

**Purpose:** Indicate loading state for async operations.

**Features:**
- Inline or full-page overlay
- Multiple sizes
- Customizable colors
- Auto-trigger on form submit

**Usage (Inline):**
```django
{% include "components/ui_loading.html" with size="sm" text="Loading..." %}
```

**Usage (Overlay):**
```django
{% include "components/ui_loading.html" with overlay=True loading_text="Processing..." %}
```

**Sizes:** xs, sm, md (default), lg, xl

**Auto-loading Forms:**
```html
<form data-loading method="post">
  <!-- Form submits show overlay automatically -->
</form>
```

---

## 🎨 Color Palette

### Primary Colors (Blue)
- `primary-50`: #eff6ff (very light)
- `primary-100`: #dbeafe (light backgrounds)
- `primary-500`: #3b82f6 (focus states)
- `primary-600`: #2563eb (buttons, primary actions)
- `primary-700`: #1d4ed8 (hover states)
- `primary-900`: #1e3a8a (dark text)

### Semantic Colors

**Success (Green)**
- `green-100`: Background for success states
- `green-600`: Text/icons for success
- `green-800`: Dark success text

**Error (Red)**
- `red-50`: Error field backgrounds
- `red-300`: Error borders
- `red-600`: Error text/icons

**Warning (Yellow)**
- `yellow-100`: Warning backgrounds
- `yellow-500`: Warning icons
- `yellow-800`: Warning text

**Info (Blue)**
- `blue-50`: Info backgrounds
- `blue-600`: Info icons/text

---

## 📐 Spacing & Typography

### Spacing Scale
- **Gap-2**: 0.5rem (8px) - Tight spacing
- **Gap-3**: 0.75rem (12px) - Standard spacing
- **Gap-4**: 1rem (16px) - Card padding
- **Gap-6**: 1.5rem (24px) - Section spacing

### Typography
- **Headings:** font-bold, text-gray-900
- **Body:** font-medium, text-gray-700
- **Labels:** font-bold, text-sm, text-gray-700
- **Subtext:** text-sm, text-gray-600

---

## 🖼️ Layout Patterns

### Card Layout
```html
<div class="bg-white rounded-lg shadow-md p-6">
  <!-- Content -->
</div>
```

### Grid Layouts
```html
<!-- 4 columns on desktop -->
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
  <!-- Items -->
</div>
```

### Form Layout
```html
<div class="max-w-2xl">
  <form>
    <div class="space-y-5">
      <!-- Form fields -->
    </div>
  </form>
</div>
```

---

## 🔧 Implementation Examples

### Complete List View with All Components

```django
{% extends "base.html" %}

{% block content %}
<!-- Breadcrumb -->
{% include "components/ui_breadcrumb.html" with items=breadcrumbs %}

<!-- Page Header -->
<div class="mb-6">
  <h1 class="text-3xl font-bold text-gray-900 mb-2">Students</h1>
  <p class="text-gray-600">Manage student records</p>
</div>

<!-- Toast Notifications -->
{% include "components/ui_toast.html" %}

<!-- Search & Filter -->
{% include "components/ui_search_filter.html" with search_placeholder="Search students..." show_export=True create_url="/students/add/" %}

<!-- Content -->
{% if students %}
  <!-- Table -->
  <div class="overflow-x-auto bg-white rounded-xl shadow-sm border border-gray-200">
    <table class="min-w-full divide-y divide-gray-200">
      <!-- Table content -->
    </table>
  </div>
  
  <!-- Pagination -->
  {% include "components/ui_pagination.html" with page_obj=page_obj %}
{% else %}
  <!-- Empty State -->
  {% include "components/ui_empty_state.html" with icon="users" title="No students found" action_url="/students/add/" %}
{% endif %}
{% endblock %}
```

### Dashboard with Stats

```django
<!-- Welcome Banner -->
<div class="bg-gradient-to-r from-primary-600 to-purple-600 rounded-xl p-6 text-white shadow-lg mb-6">
  <h1 class="text-2xl font-bold">Welcome back!</h1>
</div>

<!-- Stats Grid -->
<div class="grid grid-cols-1 md:grid-cols-4 gap-6">
  {% include "components/ui_stat_card.html" with title="Total Users" value="1,234" icon="users" color="blue" %}
  {% include "components/ui_stat_card.html" with title="Active Sessions" value="89" icon="activity" color="green" trend="up" change="+5%" %}
</div>
```

---

## ✅ Best Practices

### 1. **Consistency**
- Always use component includes instead of custom HTML
- Maintain color palette across all pages
- Use standard spacing (gap-4, gap-6)

### 2. **Accessibility**
- Include aria labels for screen readers
- Ensure proper color contrast
- Add focus states for keyboard navigation

### 3. **Responsive Design**
- Use grid/flex with responsive breakpoints
- Test on mobile (sm:), tablet (md:), desktop (lg:)
- Hide/show elements appropriately

### 4. **Performance**
- Use Tailwind's utility classes (no custom CSS)
- Minimize JavaScript for components
- Auto-dismiss notifications to prevent clutter

### 5. **User Experience**
- Show loading states for async actions
- Provide clear error messages
- Include empty states for all lists
- Add breadcrumbs for navigation context

---

## 🚀 Quick Start Checklist

When creating a new page:

- [ ] Extend from appropriate base template
- [ ] Add breadcrumb navigation
- [ ] Include toast notifications
- [ ] Use search/filter component for lists
- [ ] Add pagination if needed
- [ ] Include empty state handling
- [ ] Apply consistent card styling
- [ ] Test responsive layout
- [ ] Verify color consistency
- [ ] Check accessibility

---

## 📞 Support

For questions or custom component requests, refer to:
- `docs/UI_ENHANCEMENT_SUMMARY.md` - Overall UI improvements
- `docs/UI_ARCHITECTURE.md` - Architecture guidelines
- `templates/components/` - Component source code

**Last Updated:** March 1, 2026  
**Version:** 2.0  
**Status:** Production Ready
