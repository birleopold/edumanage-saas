from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Driver(models.Model):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ON_LEAVE = "ON_LEAVE"
    
    STATUS_CHOICES = (
        (ACTIVE, "Active"),
        (INACTIVE, "Inactive"),
        (ON_LEAVE, "On Leave"),
    )
    
    staff = models.OneToOneField("hr.StaffProfile", on_delete=models.CASCADE, null=True, blank=True, related_name="driver_profile")
    name = models.CharField(max_length=128, help_text="Driver name if not linked to staff")
    license_number = models.CharField(max_length=64, unique=True)
    license_expiry = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    emergency_contact = models.CharField(max_length=128, blank=True)
    emergency_phone = models.CharField(max_length=32, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=ACTIVE)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.staff.get_full_name() if self.staff else self.name

    def get_display_name(self):
        return str(self)


class Vehicle(models.Model):
    OPERATIONAL = "OPERATIONAL"
    MAINTENANCE = "MAINTENANCE"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"
    
    STATUS_CHOICES = (
        (OPERATIONAL, "Operational"),
        (MAINTENANCE, "Under Maintenance"),
        (OUT_OF_SERVICE, "Out of Service"),
    )
    
    BUS = "BUS"
    VAN = "VAN"
    CAR = "CAR"
    
    TYPE_CHOICES = (
        (BUS, "Bus"),
        (VAN, "Van"),
        (CAR, "Car"),
    )
    
    name = models.CharField(max_length=128)
    vehicle_type = models.CharField(max_length=16, choices=TYPE_CHOICES, default=BUS)
    plate_number = models.CharField(max_length=64, unique=True)
    capacity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    manufacture_year = models.PositiveIntegerField(null=True, blank=True)
    model = models.CharField(max_length=128, blank=True)
    color = models.CharField(max_length=64, blank=True)
    insurance_expiry = models.DateField(null=True, blank=True)
    last_maintenance = models.DateField(null=True, blank=True)
    next_maintenance = models.DateField(null=True, blank=True)
    gps_device_id = models.CharField(max_length=128, blank=True, help_text="GPS tracking device identifier")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=OPERATIONAL)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.plate_number} - {self.name}"

    def is_maintenance_due(self):
        if self.next_maintenance:
            return timezone.now().date() >= self.next_maintenance
        return False

    def available_capacity(self):
        # Calculate available seats based on active assignments
        assigned_count = StudentTransportAssignment.objects.filter(
            route__vehicle=self,
            is_active=True
        ).count()
        return self.capacity - assigned_count


class TransportRoute(models.Model):
    MORNING = "MORNING"
    AFTERNOON = "AFTERNOON"
    BOTH = "BOTH"
    
    SHIFT_CHOICES = (
        (MORNING, "Morning (Pickup)"),
        (AFTERNOON, "Afternoon (Drop-off)"),
        (BOTH, "Both"),
    )
    
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32, unique=True)
    description = models.TextField(blank=True)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name="routes")
    driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, blank=True, related_name="routes")
    shift = models.CharField(max_length=16, choices=SHIFT_CHOICES, default=BOTH)
    start_time = models.TimeField(null=True, blank=True, help_text="Route start time")
    estimated_duration = models.PositiveIntegerField(null=True, blank=True, help_text="Estimated duration in minutes")
    distance_km = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Total route distance in km")
    fare_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Monthly fare for this route")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("code", "name")

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"

    def total_students(self):
        return StudentTransportAssignment.objects.filter(route=self, is_active=True).count()

    def capacity_percentage(self):
        if self.vehicle and self.vehicle.capacity:
            total = self.total_students()
            return (total / self.vehicle.capacity) * 100
        return 0


class RouteStop(models.Model):
    route = models.ForeignKey(TransportRoute, on_delete=models.CASCADE, related_name="stops")
    name = models.CharField(max_length=128)
    order = models.PositiveSmallIntegerField(default=1, help_text="Stop sequence number")
    pickup_time = models.TimeField(null=True, blank=True)
    dropoff_time = models.TimeField(null=True, blank=True)
    location_note = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("route", "order")
        unique_together = ("route", "order")

    def __str__(self) -> str:
        return f"{self.route.code} - Stop {self.order}: {self.name}"

    def student_count(self):
        return StudentTransportAssignment.objects.filter(stop=self, is_active=True).count()


class StudentTransportAssignment(models.Model):
    PICKUP_ONLY = "PICKUP_ONLY"
    DROPOFF_ONLY = "DROPOFF_ONLY"
    BOTH = "BOTH"
    
    SERVICE_TYPE_CHOICES = (
        (PICKUP_ONLY, "Pickup Only"),
        (DROPOFF_ONLY, "Drop-off Only"),
        (BOTH, "Both Ways"),
    )
    
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE, related_name="transport_assignments")
    route = models.ForeignKey(TransportRoute, on_delete=models.CASCADE, related_name="student_assignments")
    stop = models.ForeignKey(RouteStop, on_delete=models.SET_NULL, null=True, blank=True, related_name="student_assignments")
    service_type = models.CharField(max_length=16, choices=SERVICE_TYPE_CHOICES, default=BOTH)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    monthly_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    emergency_contact = models.CharField(max_length=128, blank=True, help_text="Parent/Guardian contact for transport emergencies")
    emergency_phone = models.CharField(max_length=32, blank=True)
    special_needs = models.TextField(blank=True, help_text="Any special requirements or medical conditions")
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("route", "stop__order", "student__first_name")
        unique_together = ("student", "route")

    def __str__(self) -> str:
        return f"{self.student.get_full_name()} → {self.route.code}"

    def is_current(self):
        today = timezone.now().date()
        if self.end_date:
            return self.start_date <= today <= self.end_date
        return self.start_date <= today


class RouteSchedule(models.Model):
    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"
    
    DAY_CHOICES = (
        (MONDAY, "Monday"),
        (TUESDAY, "Tuesday"),
        (WEDNESDAY, "Wednesday"),
        (THURSDAY, "Thursday"),
        (FRIDAY, "Friday"),
        (SATURDAY, "Saturday"),
        (SUNDAY, "Sunday"),
    )
    
    route = models.ForeignKey(TransportRoute, on_delete=models.CASCADE, related_name="schedules")
    day_of_week = models.CharField(max_length=16, choices=DAY_CHOICES)
    start_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("route", "day_of_week", "start_time")
        unique_together = ("route", "day_of_week", "start_time")

    def __str__(self) -> str:
        return f"{self.route.code} - {self.get_day_of_week_display()} @ {self.start_time}"


class VehicleTracking(models.Model):
    """GPS tracking log for vehicles"""
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="tracking_logs")
    route = models.ForeignKey(TransportRoute, on_delete=models.SET_NULL, null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    speed = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Speed in km/h")
    heading = models.PositiveIntegerField(null=True, blank=True, help_text="Compass heading 0-359")
    timestamp = models.DateTimeField(auto_now_add=True)
    is_moving = models.BooleanField(default=True)

    class Meta:
        ordering = ("-timestamp",)
        indexes = [
            models.Index(fields=['vehicle', '-timestamp']),
        ]

    def __str__(self) -> str:
        return f"{self.vehicle.plate_number} @ {self.timestamp}"


class ParentNotification(models.Model):
    """Notifications sent to parents about transport"""
    PICKUP = "PICKUP"
    DROPOFF = "DROPOFF"
    DELAY = "DELAY"
    EMERGENCY = "EMERGENCY"
    GENERAL = "GENERAL"
    
    TYPE_CHOICES = (
        (PICKUP, "Pickup Notification"),
        (DROPOFF, "Drop-off Notification"),
        (DELAY, "Delay Alert"),
        (EMERGENCY, "Emergency"),
        (GENERAL, "General"),
    )
    
    assignment = models.ForeignKey(StudentTransportAssignment, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ("-sent_at",)

    def __str__(self) -> str:
        return f"{self.get_notification_type_display()} - {self.assignment.student.get_full_name()}"
