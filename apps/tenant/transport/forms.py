from django import forms

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
        
        if not staff and not name:
            raise forms.ValidationError("Either staff or name must be provided.")
        
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

    def clean(self):
        cleaned = super().clean()
        route = cleaned.get("route")
        stop = cleaned.get("stop")
        
        if stop and route and stop.route_id != route.id:
            self.add_error("stop", "Stop must belong to the selected route.")
        
        start_date = cleaned.get("start_date")
        end_date = cleaned.get("end_date")
        
        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "End date must be after start date.")
        
        return cleaned


class RouteScheduleForm(forms.ModelForm):
    class Meta:
        model = RouteSchedule
        fields = ["route", "day_of_week", "start_time", "notes", "is_active"]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class VehicleTrackingForm(forms.ModelForm):
    class Meta:
        model = VehicleTracking
        fields = ["vehicle", "route", "latitude", "longitude", "speed", "heading", "is_moving"]


class ParentNotificationForm(forms.ModelForm):
    class Meta:
        model = ParentNotification
        fields = ["assignment", "notification_type", "message"]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 4}),
        }
