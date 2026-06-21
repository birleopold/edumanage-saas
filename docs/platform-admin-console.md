# Platform Admin Console

This module exposes public-schema SaaS tenant and domain management outside raw Django admin.

## Access

- URL: `/platform/`
- Login: `/platform/login/`
- Logout: `/platform/logout/`
- Access is restricted to authenticated Django superusers only.

## Non-technical tenant onboarding

The simplest intended workflow is:

1. Buy the client's domain name.
2. Point the domain DNS to the EduManage server, proxy, or load balancer.
3. Open `/platform/tenants/create/`.
4. Enter the school name, schema name, status, and client domain name.
5. Submit the form.

The tenant and its primary custom domain are created together. The platform owner does not need to open Django admin or add the domain on a second screen.

## Included in the first rollout

- Platform dashboard with tenant/domain counts.
- Tenant list with search, status filter and pagination.
- Tenant creation and editing.
- Tenant creation with automatic primary custom domain attachment.
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
- DNS and SSL should be handled at hosting/proxy level, for example through Cloudflare, Caddy, Traefik, Nginx plus certificates, or a managed load balancer.

## Suggested verification before merge

Run Django checks and the public tenant tests using tenant settings, then smoke-test platform routes and tenant availability behavior in a tenant-aware PostgreSQL environment. Local execution was not performed in the ChatGPT tool environment.
