# Platform Admin Console

This module exposes public-schema SaaS tenant and domain management outside raw Django admin.

## Access

- URL: `/platform/`
- Login: `/platform/login/`
- Logout: `/platform/logout/`
- Access is restricted to authenticated Django superusers only.

## Included in the first rollout

- Platform dashboard with tenant/domain counts.
- Tenant list with search, status filter and pagination.
- Tenant creation and editing.
- Tenant status updates.
- Tenant detail page with schema readiness check.
- Domain creation and editing.
- Primary domain selection.
- Manual domain verification.
- Domain deletion.
- Tenant status middleware for unavailable tenant portals.
- Safer platform login redirect handling.
- Focused middleware and redirect safety tests.

## Notes

- Schema existence checks are available when running in PostgreSQL tenant mode.
- Tenant schema names are locked after creation to protect tenant data.
- Domain verification is manual in this version. A future version can automate verification using DNS records.
- The public schema remains available so platform superusers can manage tenant status from `/platform/`.

## Suggested verification before merge

Run Django checks and the public tenant tests using tenant settings, then smoke-test platform routes and tenant availability behavior in a tenant-aware PostgreSQL environment.
