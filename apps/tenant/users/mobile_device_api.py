from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import MobileDevice


class UserDeviceAPIView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]


def device_payload(device: MobileDevice):
    return {
        "id": device.id,
        "platform": device.platform,
        "device_id": device.device_id,
        "app_version": device.app_version,
        "is_active": device.is_active,
        "push_ready": bool(device.push_token and device.is_active),
        "last_seen_at": device.last_seen_at,
        "created_at": device.created_at,
    }


def normalize_platform(value):
    platform = (value or MobileDevice.WEB).upper()
    allowed = {choice[0] for choice in MobileDevice.PLATFORM_CHOICES}
    return platform if platform in allowed else MobileDevice.WEB


class UserDeviceList(UserDeviceAPIView):
    def get(self, request):
        devices = MobileDevice.objects.filter(user=request.user).order_by("-is_active", "-last_seen_at")
        return Response({"devices": [device_payload(device) for device in devices]})


class UserDeviceRegister(UserDeviceAPIView):
    def post(self, request):
        platform = normalize_platform(request.data.get("platform"))
        device_id = request.data.get("device_id") or ""
        app_version = request.data.get("app_version") or ""
        token = request.data.get("push_token") or ""

        device, created = MobileDevice.objects.update_or_create(
            user=request.user,
            platform=platform,
            device_id=device_id,
            defaults={
                "push_token": token,
                "app_version": app_version,
                "is_active": True,
                "last_seen_at": timezone.now(),
            },
        )
        return Response({"registered": created, "device": device_payload(device)}, status=status.HTTP_200_OK)


class UserDeviceTokenUpdate(UserDeviceAPIView):
    def post(self, request):
        device_id = request.data.get("device_id") or ""
        platform = normalize_platform(request.data.get("platform"))
        token = request.data.get("push_token") or ""
        app_version = request.data.get("app_version") or ""

        device, _ = MobileDevice.objects.update_or_create(
            user=request.user,
            platform=platform,
            device_id=device_id,
            defaults={
                "push_token": token,
                "app_version": app_version,
                "is_active": True,
                "last_seen_at": timezone.now(),
            },
        )
        return Response({"updated": True, "device": device_payload(device)})


class UserDeviceDisable(UserDeviceAPIView):
    def post(self, request, pk: int):
        device = get_object_or_404(MobileDevice, pk=pk, user=request.user)
        device.is_active = False
        device.push_token = ""
        device.last_seen_at = timezone.now()
        device.save(update_fields=["is_active", "push_token", "last_seen_at"])
        return Response({"disabled": True, "device": device_payload(device)})
