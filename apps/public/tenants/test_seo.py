import json
import re
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse
from django_tenants.utils import get_public_schema_name

from .seo_middleware import SearchIndexControlMiddleware
from .seo_views import (
    PUBLIC_INDEXABLE_PATHS,
    _seo_context,
    marketing_home,
    marketing_page,
    robots_txt,
    sitemap_xml,
)


@override_settings(
    ROOT_URLCONF="config.public_urls",
    SEO_CANONICAL_ORIGIN="https://edumanage.example",
    SEO_CONTACT_EMAIL="hello@edumanage.example",
    SEO_GOOGLE_SITE_VERIFICATION="google-token",
    SEO_BING_SITE_VERIFICATION="bing-token",
    SEO_GOOGLE_ANALYTICS_ID="G-TEST123",
)
class PublicSeoTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def request(self, path, *, host="edumanage.example"):
        request = self.factory.get(path, secure=True, HTTP_HOST=host)
        request.user = AnonymousUser()
        return request

    def test_marketing_home_has_complete_search_metadata(self):
        request = self.request("/")
        with patch.object(connection, "schema_name", get_public_schema_name(), create=True):
            response = marketing_home(request)
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("<h1>Run your entire school from one secure platform</h1>", body)
        self.assertIn('<link rel="canonical" href="https://edumanage.example/">', body)
        self.assertIn('<meta name="description"', body)
        self.assertIn('<meta property="og:title"', body)
        self.assertIn('<meta name="twitter:card" content="summary_large_image">', body)
        self.assertIn('name="google-site-verification" content="google-token"', body)
        self.assertIn('name="msvalidate.01" content="bing-token"', body)
        self.assertIn("G-TEST123", body)
        self.assertIn('type="application/ld+json"', body)

    def test_inner_page_has_unique_title_canonical_and_breadcrumb_schema(self):
        request = self.request("/school-management-software/")
        with patch.object(connection, "schema_name", get_public_schema_name(), create=True):
            response = marketing_page(request, "school_software")
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("Cloud School Management Software for Schools", body)
        self.assertIn(
            '<link rel="canonical" href="https://edumanage.example/school-management-software/">',
            body,
        )
        match = re.search(
            r'<script type="application/ld\+json">(.*?)</script>',
            body,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        structured_data = json.loads(match.group(1))
        graph_types = {item["@type"] for item in structured_data["@graph"]}
        self.assertIn("Organization", graph_types)
        self.assertIn("WebSite", graph_types)
        self.assertIn("WebApplication", graph_types)
        self.assertIn("BreadcrumbList", graph_types)

    def test_public_robots_allows_marketing_and_points_to_sitemap(self):
        request = self.request("/robots.txt")
        with patch.object(connection, "schema_name", get_public_schema_name(), create=True):
            response = robots_txt(request)
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("User-agent: *", body)
        self.assertIn("Allow: /", body)
        self.assertIn("Disallow: /dj-admin/", body)
        self.assertIn("Sitemap: https://edumanage.example/sitemap.xml", body)

    def test_tenant_robots_disallows_all_crawling(self):
        request = self.request("/robots.txt", host="school.example")
        with patch.object(connection, "schema_name", "school_schema", create=True):
            response = robots_txt(request)
        self.assertEqual(response.content.decode(), "User-agent: *\nDisallow: /\n")

    def test_public_sitemap_contains_every_indexable_page(self):
        request = self.request("/sitemap.xml")
        with patch.object(connection, "schema_name", get_public_schema_name(), create=True):
            response = sitemap_xml(request)
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        for path in PUBLIC_INDEXABLE_PATHS:
            self.assertIn(f"https://edumanage.example{path}", body)
        self.assertNotIn("/platform/", body)
        self.assertNotIn("/login/", body)

    def test_urlconf_exposes_expected_public_search_routes(self):
        self.assertEqual(reverse("marketing_home"), "/")
        self.assertEqual(reverse("marketing_features"), "/features/")
        self.assertEqual(reverse("marketing_school_software"), "/school-management-software/")
        self.assertEqual(reverse("sitemap_xml"), "/sitemap.xml")
        self.assertEqual(reverse("robots_txt"), "/robots.txt")

    def test_structured_data_does_not_invent_ratings_or_reviews(self):
        request = self.request("/")
        context = _seo_context(
            request,
            {
                "route_name": "marketing_home",
                "title": "EduManage",
                "description": "School management software",
            },
        )
        payload = context["structured_data"]
        self.assertNotIn("aggregateRating", payload)
        self.assertNotIn('"review"', payload)


class SearchIndexControlMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SearchIndexControlMiddleware(lambda request: HttpResponse("ok"))

    def test_public_marketing_page_is_indexable(self):
        request = self.factory.get("/")
        with patch.object(connection, "schema_name", get_public_schema_name(), create=True):
            response = self.middleware(request)
        self.assertIn("index, follow", response["X-Robots-Tag"])

    def test_platform_route_is_noindex(self):
        request = self.factory.get("/platform/")
        with patch.object(connection, "schema_name", get_public_schema_name(), create=True):
            response = self.middleware(request)
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow, noarchive")

    def test_every_tenant_application_page_is_noindex(self):
        request = self.factory.get("/")
        with patch.object(connection, "schema_name", "school_schema", create=True):
            response = self.middleware(request)
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow, noarchive")
