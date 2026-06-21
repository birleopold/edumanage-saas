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
- Tenant status updates: active, pending, suspended and archived.
- Tenant detail page with schema readiness check.
- Domain creation and editing.
- Primary domain selection.
- Manual domain verification.
- Domain deletion.

## Notes

- Schema existence checks are available when running in PostgreSQL tenant mode.
- Tenant schema names are locked after creation to protect tenant data.
- Domain verification is manual in this first version. A future version can automate verification using DNS TXT or CNAME records.
- Tenant suspension currently updates the tenant `status` field. Middleware or portal guards should later enforce access blocking for suspended/archived tenants.
