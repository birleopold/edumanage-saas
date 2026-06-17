from rest_framework.response import Response
from rest_framework.views import APIView


class MobileOpenAPISchema(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        base = "/api/v1"
        schema = {
            "openapi": "3.0.3",
            "info": {"title": "EduManage Mobile API", "version": "1.0.0"},
            "servers": [{"url": base, "description": "Current tenant API"}],
            "components": {
                "securitySchemes": {
                    "jwtAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
                }
            },
            "security": [{"jwtAuth": []}],
            "paths": {
                "/auth/token/": {"post": {"summary": "Mobile login", "tags": ["Auth"]}},
                "/auth/token/refresh/": {"post": {"summary": "Refresh mobile session", "tags": ["Auth"]}},
                "/mobile/me/": {"get": {"summary": "Current user profile", "tags": ["Profile"]}},
                "/mobile/dashboard/": {"get": {"summary": "Role-based mobile dashboard", "tags": ["Dashboard"]}},
                "/mobile/students/": {"get": {"summary": "Students scoped to current user", "tags": ["Students"]}},
                "/mobile/teachers/": {"get": {"summary": "Active teachers", "tags": ["Teachers"]}},
                "/mobile/parents/": {"get": {"summary": "Parent and linked students", "tags": ["Parents"]}},
                "/mobile/attendance/": {"get": {"summary": "Attendance list or teacher attendance context", "tags": ["Attendance"]}},
                "/mobile/attendance/offerings/{offering_id}/mark/": {"post": {"summary": "Teacher marks attendance from mobile", "tags": ["Attendance"]}},
                "/mobile/finance/": {"get": {"summary": "Invoices, balances, and payments", "tags": ["Finance"]}},
                "/mobile/finance/payment-requests/": {"get": {"summary": "Mobile payment request status", "tags": ["Finance"]}},
                "/mobile/finance/invoices/{invoice_id}/pay/": {"post": {"summary": "Start mobile payment request", "tags": ["Finance"]}},
                "/mobile/exams/": {"get": {"summary": "Exam papers, attempts, and published results", "tags": ["Exams"]}},
                "/mobile/coursework/": {"get": {"summary": "Coursework materials and assignments", "tags": ["Coursework"]}},
                "/mobile/messages/": {"get": {"summary": "Conversations and announcements", "tags": ["Messages"]}},
                "/mobile/transport/": {"get": {"summary": "Student transport assignments", "tags": ["Transport"]}},
                "/mobile/devices/register/": {"post": {"summary": "Register mobile device for notifications", "tags": ["Notifications"]}},
            },
        }
        return Response(schema)
