# Logo Upload Feature - Complete Guide

## Overview

When you upload a logo at `/admin/settings/`, it becomes your school's **visual brand identity** across the entire system. The logo appears in multiple locations and serves several important purposes.

---

## Where Your Logo Appears

### **1. Admin Portal Sidebar** 🎯
**Location:** Left sidebar on every admin page

**How it works:**
- Logo displays at the top of the sidebar
- Shows with glassmorphism design (frosted glass effect)
- Has rounded corners and shadow
- Bordered with your primary color

**Priority:**
1. If campus has `logo_override` → Use campus logo
2. Else if organization has `logo` → Use organization logo
3. Else → Show default graduation cap icon

**Code:** `templates/portals/admin/base.html:126-132`

---

### **2. Teacher Portal Sidebar**
**Location:** Left sidebar on every teacher page

**Same behavior as admin portal:**
- Campus logo override takes priority
- Falls back to organization logo
- Default icon if no logo uploaded

**Code:** `templates/portals/teacher/base.html`

---

### **3. Student Portal Sidebar**
**Location:** Left sidebar on every student page

**Same behavior:**
- Shows your school branding
- Helps students identify they're on the right platform
- Professional appearance

**Code:** `templates/portals/student/base.html`

---

### **4. Parent Portal Sidebar**
**Location:** Left sidebar on every parent page

**Same behavior:**
- Parents see your school's logo
- Builds trust and recognition
- Consistent branding across all portals

**Code:** `templates/portals/parent/base.html`

---

### **5. Landing Page / Public Website**
**Location:** Top navigation bar on landing page

**How it works:**
- Displays in the header/navbar
- First thing visitors see
- Represents your school to prospective students/parents

**Code:** `templates/landing.html:55-59`

---

### **6. Report Cards & Documents** (Future)
**Planned usage:**
- PDF report cards
- Official transcripts
- Certificates
- Letters to parents
- Invoices

---

## Logo Types & Formats

### **Supported Formats:**
✅ **SVG** (Recommended) - Scalable, looks sharp at any size  
✅ **PNG** - Good for logos with transparency  
✅ **JPG/JPEG** - Works but no transparency  
✅ **GIF** - Supported but not recommended  

### **Best Practices:**

#### **For SVG:**
- ✅ Best choice for logos
- ✅ Scales perfectly (no pixelation)
- ✅ Small file size
- ✅ Looks crisp on any screen
- ✅ Works on retina displays

#### **For PNG:**
- ✅ Use if you have transparency
- ✅ Recommended size: 500px wide minimum
- ✅ Keep file size under 500KB
- ✅ Use transparent background

#### **For JPG:**
- ⚠️ No transparency (white background shows)
- ⚠️ Can look pixelated when scaled
- ✅ Smaller file size than PNG

---

## Two-Level Logo System

Your system supports **two levels** of branding:

### **1. Organization Logo** (Global)
**Set at:** `/admin/settings/` → Organization Profile

**Applies to:**
- All campuses by default
- Landing page
- System-wide branding
- Default for all portals

**Model:** `OrganizationProfile.logo`

---

### **2. Campus Logo Override** (Per-Campus)
**Set at:** `/admin/settings/campuses/` → Edit Campus

**Applies to:**
- Specific campus only
- Overrides organization logo
- Useful for multi-campus schools

**Model:** `Campus.logo_override`

**Example use case:**
- Main School: Uses organization logo
- Branch Campus: Has its own logo via `logo_override`

---

## How It Works Technically

### **Upload Process:**

1. **Admin uploads logo** at `/admin/settings/`
2. **File is saved** to: `{tenant_schema}/branding/{filename}`
3. **Database stores** file path in `OrganizationProfile.logo`
4. **Context processor** makes logo available to all templates
5. **Templates display** logo using `{{ org_profile.logo.url }}`

### **Context Processor:**
**File:** `apps/tenant/orgsettings/context_processors.py`

Makes these variables available to ALL templates:
```python
{
    'org_profile': OrganizationProfile object,  # Has .logo field
    'current_campus': Campus object,            # Has .logo_override field
    'campuses': List of campuses,
    'feature_flags': Feature flags,
    'cache_buster': Timestamp for cache busting
}
```

### **Template Logic:**
```django
{% if current_campus and current_campus.logo_override %}
    <!-- Use campus-specific logo -->
    <img src="{{ current_campus.logo_override.url }}" />
{% elif org_profile and org_profile.logo %}
    <!-- Use organization logo -->
    <img src="{{ org_profile.logo.url }}" />
{% else %}
    <!-- Show default icon -->
    <i class="ph ph-graduation-cap"></i>
{% endif %}
```

---

## Benefits of Uploading a Logo

### **1. Professional Appearance** 🎨
- Makes your school look established
- Builds credibility with parents
- Students recognize the platform

### **2. Brand Consistency** 🏫
- Same logo across all portals
- Consistent experience for all users
- Reinforces school identity

### **3. Trust & Recognition** ✅
- Parents trust official-looking platforms
- Students feel they're in the right place
- Reduces confusion

### **4. Multi-Tenant Isolation** 🔒
- Each school has its own logo
- No confusion between different schools
- Professional multi-school setup

### **5. White-Label Ready** 🎯
- Can rebrand for different schools
- Campus-specific branding
- Franchise-ready

---

## Color Branding (Bonus)

Along with the logo, you can also set:

### **Primary Color**
- Used for buttons, links, highlights
- Appears in sidebar borders
- Accent color throughout UI

### **Secondary Color**
- Supporting color
- Used for secondary elements
- Complements primary color

**Set at:** `/admin/settings/` → Organization Profile

**Example:**
- Primary: `#1E40AF` (Blue)
- Secondary: `#10B981` (Green)

These colors work together with your logo to create a cohesive brand identity.

---

## File Storage

### **Storage Location:**
```
media/
└── {tenant_schema}/
    └── branding/
        ├── school_logo.svg
        ├── campus_east_logo.png
        └── campus_west_logo.jpg
```

### **Multi-Tenant Isolation:**
- Each school (tenant) has its own folder
- Logos are isolated by schema name
- No cross-contamination between schools

### **Function:**
```python
def branding_upload_to(instance, filename: str) -> str:
    schema = connection.schema_name or "public"
    return f"{schema}/branding/{filename}"
```

---

## Step-by-Step: How to Upload a Logo

### **For Organization Logo:**

1. **Navigate to Settings**
   - Go to `/admin/settings/`
   - Or click "Settings" in admin sidebar

2. **Upload Logo**
   - Click "Choose File" under Logo field
   - Select your logo file (SVG, PNG, or JPG)
   - Click "Save"

3. **Verify**
   - Refresh any page
   - Check sidebar - logo should appear
   - Check landing page - logo should appear

### **For Campus-Specific Logo:**

1. **Navigate to Campuses**
   - Go to `/admin/settings/campuses/`
   - Click "Edit" on the campus

2. **Upload Logo Override**
   - Scroll to "Logo Override" field
   - Click "Choose File"
   - Select campus-specific logo
   - Click "Save"

3. **Verify**
   - Switch to that campus
   - Logo should change to campus-specific one

---

## Troubleshooting

### **Logo Not Showing?**

**Check:**
1. ✅ File was uploaded successfully
2. ✅ File format is supported (SVG, PNG, JPG)
3. ✅ File size is reasonable (< 5MB)
4. ✅ Media files are being served correctly
5. ✅ Clear browser cache (Ctrl+F5)

**Common Issues:**
- **White screen:** File too large
- **Broken image:** Media URL not configured
- **Old logo shows:** Browser cache (clear it)

### **Logo Looks Pixelated?**

**Solutions:**
- Use SVG format (scales perfectly)
- Use larger PNG (min 500px wide)
- Avoid JPG for logos with text

### **Logo Has White Background?**

**Solutions:**
- Use PNG with transparency
- Use SVG (supports transparency)
- Avoid JPG (no transparency support)

---

## Advanced: Campus-Specific Branding

If you run **multiple campuses**, each can have its own branding:

### **Example Setup:**

**Main Campus:**
- Uses organization logo
- Primary color: Blue (#1E40AF)

**East Campus:**
- Logo override: east_campus_logo.svg
- Primary color override: Green (#10B981)

**West Campus:**
- Logo override: west_campus_logo.svg
- Primary color override: Red (#DC2626)

**Result:**
- When admin switches campus, branding changes
- Each campus maintains its identity
- Centralized management

---

## Future Enhancements

### **Planned Features:**

1. **Email Templates** 📧
   - Logo in email headers
   - Branded notifications
   - Professional communications

2. **PDF Documents** 📄
   - Report cards with logo
   - Transcripts with logo
   - Certificates with logo
   - Invoices with logo

3. **Mobile App** 📱
   - Logo in app header
   - Splash screen branding
   - Push notification icon

4. **Public Portal** 🌐
   - Student registration forms
   - Parent portal login
   - Public website

5. **Print Materials** 🖨️
   - ID cards with logo
   - Letterheads
   - Certificates
   - Badges

---

## Summary

### **What Happens When You Upload a Logo:**

1. ✅ **Appears in admin sidebar** - Every admin page
2. ✅ **Appears in teacher sidebar** - Every teacher page
3. ✅ **Appears in student sidebar** - Every student page
4. ✅ **Appears in parent sidebar** - Every parent page
5. ✅ **Appears on landing page** - Public-facing website
6. ✅ **Builds brand identity** - Professional appearance
7. ✅ **Increases trust** - Parents and students recognize official platform
8. ✅ **Enables multi-campus** - Different logos per campus
9. ✅ **Future-ready** - Will appear in PDFs, emails, etc.

### **Recommended Logo Specs:**

- **Format:** SVG (preferred) or PNG
- **Size:** 500px wide minimum
- **Background:** Transparent
- **File Size:** Under 500KB
- **Aspect Ratio:** Horizontal (wider than tall)
- **Colors:** Match your school colors

---

## Quick Reference

| Feature | Organization Logo | Campus Logo Override |
|---------|------------------|---------------------|
| **Set At** | `/admin/settings/` | `/admin/settings/campuses/` |
| **Scope** | All campuses | Specific campus only |
| **Priority** | Lower | Higher (overrides org) |
| **Model Field** | `OrganizationProfile.logo` | `Campus.logo_override` |
| **Use Case** | Single campus schools | Multi-campus schools |

---

**Your logo is the face of your school in the digital world. Upload one to make your platform truly yours!** 🎓
