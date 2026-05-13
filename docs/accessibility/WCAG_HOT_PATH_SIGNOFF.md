# WCAG 2.1 AA — hot-path implementation sign-off (EduManage SaaS)

This document records accessibility work **in scope for the professional UX roadmap** (admin, teacher, parent, and student portals; public status; authentication surfaces; shared components). It is **not** a legal conformance claim for every screen in the entire product until those screens are reviewed the same way.

**Target:** WCAG 2.1 Level **AA** behaviours on the surfaces below, aligned with:

- **1.3.1** Info and Relationships (landmarks, labels, headings).
- **1.4.1** Use of Color (messages use icon + text, not color alone).
- **2.1.1** Keyboard (interactive controls operable without pointer).
- **2.4.1** Bypass Blocks (skip links on portal layouts).
- **2.4.7** Focus Visible (`:focus-visible` in portal polish + public patterns).
- **3.3.1** Error Identification (form errors and flashes exposed to assistive tech).
- **4.1.2** Name, Role, Value (buttons, regions, live regions).

## In-scope templates and components

| Area | Files / patterns |
|------|------------------|
| Admin portal | `templates/portals/admin/base.html`, `admin/home.html`, `admin/experience/communication_center.html`, `admin/students/bulk_import*.html` |
| Teacher / parent / student portals | `templates/portals/{teacher,parent,student}/base.html`, dashboard `home.html` |
| Auth | Full `templates/auth/` surface (except `password_reset_email.html`): `login.html`, `base_auth.html` (shared shell), `password_reset.html`, `password_reset_confirm.html`, `password_reset_done.html`, `password_reset_complete.html`, `setup_password.html`, `setup_expired.html`, `change_password.html`, `profile.html` |
| Public status | `templates/public/status.html` |
| Shared UI | `templates/components/ui_portal_polish.html`, `templates/components/ui_public_polish.html`, `templates/components/ui_toast.html`, `components/admin_product_tour.html` |

## Verified behaviours (by checklist)

1. **`lang="en"`** on HTML shell for listed layouts.
2. **Skip link** → `#main-content` (portals) / `#status-main` (public status) / `#auth-main` (authentication pages using `base_auth.html` or standalone login).
3. **Landmarks:** `main` with id (`#main-content` portals, `#status-main` public status, **`#auth-main`** on login and `base_auth.html` flows); side `nav` with `role="navigation"` and distinct `aria-label` per portal; notification dropdown container `role="region"` `aria-label="Notifications list"`.
4. **Messages:** `role="alert"` + `aria-live="assertive"` for **error/danger**; `role="status"` + `aria-live="polite"` for **success, warning, info**; dedicated **warning** styling (amber) + icon; notification list wrapper `aria-label="Notifications"`.
5. **Icon-only controls:** `type="button"` where applicable; **notifications** `aria-label` includes unread count when present; **profile** initials link `aria-label="Open account profile"`; **log out** `aria-label="Log out"`; search submit buttons labeled.
6. **Forms:** Bulk import file control **label / `for` / `aria-describedby`**; **authentication and profile** field error lists use **`role="alert"`** and **`aria-live="assertive"`** where shown; login non-field errors use the same pattern.
7. **Decorative graphics:** Phosphor icons **`aria-hidden="true"`** on hot-path cards and nav; logo images use **`alt`** appropriately (decorative where school name is adjacent).
8. **Keyboard focus:** `aside nav` + `main` focus rings via `ui_portal_polish.html`; public login via `ui_public_polish.html`; public status **link** `:focus-visible`.
9. **Dynamic content:** `ui_toast.html` uses severity-appropriate **`role` / `aria-live`**; SVG icons **`focusable="false"`** where used in toasts.
10. **Product tour:** Dialog **`role="dialog"`**, **`aria-modal`**, **`aria-labelledby` / `aria-describedby`**, initial focus to panel.

## Out of scope (until separately reviewed)

- Every legacy CRUD screen, PDF viewers, third-party embeds, and email-only content.
- Automated **contrast** verification of user-supplied **org colors** (campus/org overrides); tenants choosing extreme combinations should be advised in ops docs.
- Full mobile/native app audits.

## Maintenance

When adding a **new top-level portal template**, mirror: skip link, `main` id, nav `aria-label`, message live-region pattern, and `aria-hidden` on decorative icons.

**Sign-off (roadmap):** The roadmap item *“WCAG audit (contrast, forms, ARIA)”* is marked **Done** for this **hot-path** scope as defined above; product-wide audits are incremental extensions of the same checklist.
