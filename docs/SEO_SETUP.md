# EduManage SEO setup

EduManage includes a technical SEO foundation for the public marketing domain. Private school portals, platform administration, APIs and authenticated application pages are intentionally excluded from indexing.

## Public indexable pages

- `/`
- `/features/`
- `/school-management-software/`
- `/pricing/`
- `/contact/`
- `/privacy/`
- `/terms/`

The public sitemap is available at `/sitemap.xml` and crawler rules are available at `/robots.txt`.

## Environment options

```env
SEO_SITE_NAME=EduManage
SEO_SITE_ALTERNATE_NAME=EduManage School Management System
SEO_ORGANIZATION_NAME=EduManage
SEO_CANONICAL_ORIGIN=https://edumanage.leosoftug.com
SEO_CONTACT_EMAIL=admin@leosoftug.com
SEO_LOCALE=en_UG
SEO_DEFAULT_IMAGE_URL=https://edumanage.leosoftug.com/static/img/your-1200x630-social-card.png
SEO_LOGO_URL=https://edumanage.leosoftug.com/static/img/your-logo.png
SEO_GOOGLE_SITE_VERIFICATION=
SEO_BING_SITE_VERIFICATION=
SEO_GOOGLE_ANALYTICS_ID=
```

Use a public 1200 × 630 PNG or JPEG for `SEO_DEFAULT_IMAGE_URL` when a branded social-sharing image is available. Do not use private media URLs.

## Google Search Console

1. Add the canonical domain as a Domain property or URL-prefix property.
2. Complete verification. For URL-prefix verification, paste the verification token into `SEO_GOOGLE_SITE_VERIFICATION` and restart the application.
3. Submit `https://edumanage.leosoftug.com/sitemap.xml`.
4. Inspect the homepage and the school-management-software page.
5. Request indexing after the deployment is confirmed.
6. Review indexing, Core Web Vitals, search queries and manual actions regularly.

## Bing Webmaster Tools

1. Add the canonical domain.
2. Import the verified property from Google Search Console or set `SEO_BING_SITE_VERIFICATION`.
3. Submit the same sitemap.
4. Review crawl errors and indexed-page reports.

## Analytics

Set a GA4 measurement ID such as `G-XXXXXXXXXX` in `SEO_GOOGLE_ANALYTICS_ID`. The public marketing template loads the Google tag only when this value exists. School dashboards and tenant-private pages do not need marketing analytics to be indexable.

## Structured data

The public marketing pages emit truthful JSON-LD for:

- `Organization`
- `WebSite`
- `WebApplication`
- `BreadcrumbList` on inner pages

No rating, review or price markup is invented. Validate deployed pages with Google Rich Results Test and Schema.org Validator after configuration changes.

## Ongoing ranking work

Technical SEO makes the site understandable and indexable, but rankings also depend on content quality, authority, relevance and user experience. Continue with:

- Original articles answering school-management questions
- Product screenshots and explanatory videos
- Case studies with permission from real schools
- Country and institution-type landing pages only when each page contains unique useful content
- Reputable education-sector links and partnerships
- Fast pages, stable layouts and accessible navigation
- Updated contact, privacy and service information

Avoid copied articles, keyword stuffing, fake reviews, purchased spam links and hundreds of near-duplicate location pages.

## Verification commands

```bash
curl -I https://edumanage.leosoftug.com/
curl -s https://edumanage.leosoftug.com/robots.txt
curl -s https://edumanage.leosoftug.com/sitemap.xml
curl -I https://edumanage.leosoftug.com/platform/login/
```

Expected results:

- Public marketing pages return an index/follow `X-Robots-Tag`.
- Platform and tenant-private pages return `noindex, nofollow, noarchive`.
- The sitemap contains only the seven public marketing URLs.
- Tenant domains return `Disallow: /` from `robots.txt`.
