from decimal import Decimal, InvalidOperation

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.tenant.finance.invoicing import invoice_amounts
from apps.tenant.finance.models import Invoice, MobilePaymentRequest, Payment

from .mobile_api_views import students_for_mobile_user


class MobilePaymentStart(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, invoice_id: int):
        invoice = get_object_or_404(Invoice.objects.prefetch_related("lines", "payments"), pk=invoice_id, student__in=students_for_mobile_user(request.user))
        amounts = invoice_amounts(invoice)
        try:
            amount = Decimal(str(request.data.get("amount") or amounts.balance))
        except (InvalidOperation, ValueError):
            return Response({"detail": "Invalid amount."}, status=status.HTTP_400_BAD_REQUEST)
        if amount <= 0:
            return Response({"detail": "Amount must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)
        if amount > amounts.balance:
            return Response({"detail": "Amount cannot exceed invoice balance."}, status=status.HTTP_400_BAD_REQUEST)
        phone = (request.data.get("phone_number") or "").strip()
        if not phone:
            return Response({"detail": "Phone number is required."}, status=status.HTTP_400_BAD_REQUEST)
        network = request.data.get("network") or Payment.MTN_MOMO
        request_obj = MobilePaymentRequest.objects.create(invoice=invoice, amount=amount, phone_number=phone, network=network, requested_by=request.user, provider_reference=f"MPR-{invoice.id}-{request.user.id}")
        return Response({"id": request_obj.id, "invoice_id": invoice.id, "amount": request_obj.amount, "phone_number": request_obj.phone_number, "network": request_obj.network, "status": request_obj.status, "provider_reference": request_obj.provider_reference}, status=status.HTTP_201_CREATED)


class MobilePaymentRequests(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = MobilePaymentRequest.objects.filter(invoice__student__in=students_for_mobile_user(request.user)).select_related("invoice", "invoice__student")[:100]
        return Response({"requests": [{"id": obj.id, "invoice_id": obj.invoice_id, "student": obj.invoice.student.get_full_name(), "amount": obj.amount, "phone_number": obj.phone_number, "network": obj.network, "status": obj.status, "provider_reference": obj.provider_reference, "created_at": obj.created_at} for obj in qs]})
