from django.urls import path
from rest_framework.response import Response
from rest_framework.views import APIView


class WhoAmI(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"tenant": str(getattr(request, "tenant", ""))})


urlpatterns = [
    path("whoami/", WhoAmI.as_view(), name="api_whoami"),
]
