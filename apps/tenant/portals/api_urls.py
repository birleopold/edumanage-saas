from django.urls import path
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView

from .integration_api_views import (
    IntegrationHealth,
    IntegrationMessageLogs,
    IntegrationWebhookDeliveries,
    WhatsAppStatusCallback,
)
from .mobile_api_views import (
    MobileAttendance,
    MobileCoursework,
    MobileDashboard,
    MobileDeviceRegister,
    MobileDocs,
    MobileExams,
    MobileFinance,
    MobileMe,
    MobileMessages,
    MobileParents,
    MobileStudents,
    MobileTeacherAttendanceMark,
    MobileTeachers,
    MobileTransport,
)


class WhoAmI(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"tenant": str(getattr(request, "tenant", ""))})


urlpatterns = [
    path("whoami/", WhoAmI.as_view(), name="api_whoami"),
    path("auth/token/", TokenObtainPairView.as_view(), name="api_token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="api_token_refresh"),
    path("auth/token/verify/", TokenVerifyView.as_view(), name="api_token_verify"),
    path("mobile/docs/", MobileDocs.as_view(), name="api_mobile_docs"),
    path("mobile/me/", MobileMe.as_view(), name="api_mobile_me"),
    path("mobile/dashboard/", MobileDashboard.as_view(), name="api_mobile_dashboard"),
    path("mobile/students/", MobileStudents.as_view(), name="api_mobile_students"),
    path("mobile/teachers/", MobileTeachers.as_view(), name="api_mobile_teachers"),
    path("mobile/parents/", MobileParents.as_view(), name="api_mobile_parents"),
    path("mobile/attendance/", MobileAttendance.as_view(), name="api_mobile_attendance"),
    path("mobile/attendance/offerings/<int:offering_id>/mark/", MobileTeacherAttendanceMark.as_view(), name="api_mobile_teacher_attendance_mark"),
    path("mobile/finance/", MobileFinance.as_view(), name="api_mobile_finance"),
    path("mobile/exams/", MobileExams.as_view(), name="api_mobile_exams"),
    path("mobile/coursework/", MobileCoursework.as_view(), name="api_mobile_coursework"),
    path("mobile/messages/", MobileMessages.as_view(), name="api_mobile_messages"),
    path("mobile/transport/", MobileTransport.as_view(), name="api_mobile_transport"),
    path("mobile/devices/register/", MobileDeviceRegister.as_view(), name="api_mobile_device_register"),
    path("integrations/health/", IntegrationHealth.as_view(), name="api_integrations_health"),
    path("integrations/message-logs/", IntegrationMessageLogs.as_view(), name="api_integrations_message_logs"),
    path("integrations/webhook-deliveries/", IntegrationWebhookDeliveries.as_view(), name="api_integrations_webhook_deliveries"),
    path("integrations/callbacks/whatsapp-status/", WhatsAppStatusCallback.as_view(), name="api_integrations_callback_whatsapp_status"),
]
