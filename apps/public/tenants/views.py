from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone


def health(request):
    return JsonResponse(
        {
            "status": "ok",
            "service": "edumanage",
            "time": timezone.now().isoformat(),
            "environment": getattr(settings, "ENVIRONMENT", "unknown"),
        }
    )
