from django import forms
from django.utils import timezone

from .models import (
    Driver,
    ParentNotification,
    RouteSchedule,
    RouteStop,
    StudentTransportAssignment,
    TransportRoute,
    Vehicle,
    VehicleTracking,
)


class DriverForm(forms.ModelForm):
    class Meta:
        model = Driver
        fields = [
            "staff",
            "name",
            "license_number",
            "license_expiry",
            "phone",
            "email",
            "address",
            "emergency_contact",
            "emergency_phone",
            "status",
            "notes",
            "is_active",
        ]
        widgets = {
            "license_expiry": forms.DateInput(attrs={"type": "date"}),
            "address": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        staff = cleaned.get("staff")
        name = cleaned.get("name")
        license_expiry = cleaned.get("license_expiry")
        status = cleaned.get("status")
        if not staff and not name:
            raise forms.ValidationError("Either staff or name must be provided.")
        if status == Driver.ACTIVE and license_expiry and license_expiry < timezone.localdate():
            self.add_error("license_expiry", "An active driver cannot have an expired licence.")
        return cleaned


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = [
            "name",
            "vehicle_type",
            "plate_number",
            "capacity",
            "manufacture_year",
            "model",
            "color",
            "insurance_expiry",
            "last_maintenance",
            "next_maintenance",
            "gps_device_id",
            "status",
            "notes",
            "is_active",
        ]
        widgets = {
            "insurance_expiry": forms.DateInput(attrs={"type": "date"}),
            "last_maintenance": forms.DateInput(attrs={"type": "date"}),
            "next_maintenance": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        insurance_expiry = cleaned.get("insurance_expiry")
        last_maintenance = cleaned.get("last_maintenance")
        next_maintenance = cleaned.get("next_maintenance")
        if last_maintenance and next_maintenance and next_maintenance < last_maintenance:
            self.add_error("next_maintenance", "Next maintenance cannot be before last maintenance.")
        if status == Vehicle.OPERATIONAL and insurance_expiry and insurance_expiry < timezone.localdate():
            self.add_error("insurance_expiry", "An operational vehicle cannot have expired insurance.")
        return cleaned


class TransportRouteForm(forms.ModelForm):
    class Meta:
        model = TransportRoute
        fields = [
            "name",
            "code",
            "description",
            "vehicle",
            "driver",
            "shift",
            "start_time",
            "estimated_duration",
            "distance_km",
            "fare_amount",
            "is_active",
        ]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        vehicle = cleaned.get("vehicle")
        driver = cleaned.get("driver")
        is_active = cleaned.get("is_active")
        if is_active and vehicle and vehicle.status != Vehicle.OPERATIONAL:
            self.add_error("vehicle", "Active routes must use an operational vehicle.")
        if is_active and driver and driver.status != Driver.ACTIVE:
            self.add_error("driver", "Active routes must use an active driver.")
        return cleaned


class RouteStopForm(forms.ModelForm):
    class Meta:
        model = RouteStop
        fields = [
            "route",
            "name",
            "order",
            "pickup_time",
            "dropoff_time",
            "location_note",
            "latitude",
            "longitude",
            "is_active",
        ]
        widgets = {
            "pickup_time": forms.TimeInput(attrs={"type": "time"}),
            "dropoff_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def clean(self):
        cleaned = super().clean()
        route = cleaned.get("route")
        pickup_time = cleaned.get("pickup_time")
        dropoff_time = cleaned.get("dropoff_time")
        if route and not route.is_active and cleaned.get("is_active"):
            self.add_error("route", "Cannot add an active stop to an inactive route.")
        if pickup_time and dropoff_time and pickup_time >= dropoff_time:
            self.add_error("dropoff_time", "Drop-off time should be after pickup time.")
        return cleaned


class StudentTransportAssignmentForm(forms.ModelForm):
    class Meta:
        model = StudentTransportAssignment
        fields = [
            "student",
            "route",
            "stop",
            "service_type",
            "start_date",
            "end_date",
            "monthly_fee",
            "emergency_contact",
            "emergency_phone",
            "special_needs",
            "notes",
            "is_active",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "special_needs": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        campus_scope = kwargs.pop("campus_scope", None)
        super().__init__(*args, **kwargs)
        if campus_scope:
            self.fields["student"].queryset = self.fields["student"].queryset.filter(campus=campus_scope)

    def clean(self):
        cleaned = super().clean()
        student = cleaned.get("student")
        route = cleaned.get("route")
        stop = cleaned.get("stop")
        start_date = cleaned.get("start_date")
        end_date = cleaned.get("end_date")
        is_active = cleaned.get("is_active")

        if stop and route and stop.route_id != route.id:
            self.add_error("stop", "Stop must belong to the selected route.")
        if route and is_active and not route.is_active:
            self.add_error("route", "Cannot assign a student to an inactive route.")
        if stop and is_active and not stop.is_active:
            self.add_error("stop", "Cannot assign a student to an inactive stop.")
        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "End date must be after start date.")

        if student and route and is_active:
            existing = StudentTransportAssignment.objects.filter(student=student, is_active=True)
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                self.add_error("student", "This student already has an active transport assignment.")

            vehicle = route.vehicle
            if vehicle and vehicle.capacity:
                assigned = StudentTransportAssignment.objects.filter(route=route, is_active=True)
                if self.instance and self.instance.pk:
                    assigned = assigned.exclude(pk=self.instance.pk)
                if assigned.count() >= vehicle.capacity:
                    self.add_error("route", "This route vehicle has no available seats.")

        return cleaned


class RouteScheduleForm(forms.ModelForm):
    class Meta:
        model = RouteSchedule
        fields = ["route", "day_of_week", "start_time", "notes", "is_active"]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned = super().clean()
        route = cleaned.get("route")
        if route and cleaned.get("is_active") and not route.is_active:
            self.add_error("route", "Cannot create an active schedule for an inactive route.")
        return cleaned


class VehicleTrackingForm(forms.ModelForm):
    class Meta:
        model = VehicleTracking
        fields = ["vehicle", "route", "latitude", "longitude", "speed", "heading", "is_moving"]

    def clean(self):
        cleaned = super().clean()
        vehicle = cleaned.get("vehicle")
        route = cleaned.get("route")
        if route and vehicle and route.vehicle_id and route.vehicle_id != vehicle.id:
            self.add_error("route", "Selected route does not use the selected vehicle.")
        return cleaned


class ParentNotificationForm(forms.ModelForm):
    class Meta:
        model = ParentNotification
        fields = ["assignment", "notification_type", "message"]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 4}),
        }
