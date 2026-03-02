from django.db import models


class Vehicle(models.Model):
    name = models.CharField(max_length=128)
    plate_number = models.CharField(max_length=64, blank=True)
    capacity = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)
        unique_together = ("name", "plate_number")

    def __str__(self) -> str:
        return f"{self.plate_number} - {self.name}" if self.plate_number else self.name


class TransportRoute(models.Model):
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32, blank=True)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)
        unique_together = ("name", "code")

    def __str__(self) -> str:
        return f"{self.code} - {self.name}" if self.code else self.name


class RouteStop(models.Model):
    route = models.ForeignKey(TransportRoute, on_delete=models.CASCADE, related_name="stops")
    name = models.CharField(max_length=128)
    order = models.PositiveSmallIntegerField(default=1)
    pickup_time = models.TimeField(null=True, blank=True)
    dropoff_time = models.TimeField(null=True, blank=True)
    location_note = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("route__name", "order", "name")
        unique_together = ("route", "order")

    def __str__(self) -> str:
        return f"{self.route} - {self.name}"


class StudentTransportAssignment(models.Model):
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    route = models.ForeignKey(TransportRoute, on_delete=models.CASCADE)
    stop = models.ForeignKey(RouteStop, on_delete=models.SET_NULL, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        unique_together = ("student", "route")

    def __str__(self) -> str:
        return f"{self.student} -> {self.route}"
