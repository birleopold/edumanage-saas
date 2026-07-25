from django.conf import settings
from django.db import connection
from django_tenants.utils import get_public_schema_name

from .seo_views import PUBLIC_INDEXABLE_PATHS


class SearchIndexControlMiddleware:
    """Keep private SaaS routes out of search while allowing marketing pages."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path

        static_prefix = f"/{settings.STATIC_URL.strip('/')}/"
        media_prefix = f"/{settings.MEDIA_URL.strip('/')}/"
        if path.startswith((static_prefix, media_prefix)):
            return response

        if path in {"/robots.txt", "/sitemap.xml"}:
            return response

        schema_name = getattr(connection, "schema_name", get_public_schema_name())
        public_marketing_page = (
            schema_name == get_public_schema_name()
            and path in PUBLIC_INDEXABLE_PATHS
            and response.status_code == 200
        )

        if public_marketing_page:
            response["X-Robots-Tag"] = (
                "index, follow, max-image-preview:large, "
                "max-snippet:-1, max-video-preview:-1"
            )
            response.setdefault("Content-Language", "en")
        else:
            response["X-Robots-Tag"] = "noindex, nofollow, noarchive"

        return response
