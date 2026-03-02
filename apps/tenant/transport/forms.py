from django import forms

from .models import RouteStop, StudentTransportAssignment, TransportRoute, Vehicle


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ["name", "plate_number", "capacity", "is_active"]


class TransportRouteForm(forms.ModelForm):
    class Meta:
        model = TransportRoute
        fields = ["name", "code", "vehicle", "is_active"]


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
            "is_active",
        ]
        widgets = {
            "pickup_time": forms.TimeInput(attrs={"type": "time", "placeholder": "HH:MM"}),
            "dropoff_time": forms.TimeInput(attrs={"type": "time", "placeholder": "HH:MM"}),
        }


class StudentTransportAssignmentForm(forms.ModelForm):
    class Meta:
        model = StudentTransportAssignment
        fields = [
            "student",
            "route",
            "stop",
            "start_date",
            "end_date",
            "is_active",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
            "end_date": forms.DateInput(attrs={"type": "date", "placeholder": "YYYY-MM-DD"}),
        }

    def clean(self):
        cleaned = super().clean()
        route = cleaned.get("route")
        stop = cleaned.get("stop")
        if stop and route and stop.route_id != route.id:
            self.add_error("stop", "Stop must belong to the selected route.")
        return cleaned
