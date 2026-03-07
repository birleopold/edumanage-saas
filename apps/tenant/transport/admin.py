from django.contrib import admin

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


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ('get_display_name', 'license_number', 'status', 'phone', 'is_active')
    list_filter = ('status', 'is_active')
    search_fields = ('name', 'license_number', 'phone', 'staff__first_name', 'staff__last_name')
    raw_id_fields = ('staff',)


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('name', 'plate_number', 'vehicle_type', 'capacity', 'status', 'is_active')
    list_filter = ('vehicle_type', 'status', 'is_active')
    search_fields = ('name', 'plate_number', 'model')
    date_hierarchy = 'created_at'


@admin.register(TransportRoute)
class TransportRouteAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'vehicle', 'driver', 'shift', 'is_active')
    list_filter = ('shift', 'is_active')
    search_fields = ('name', 'code', 'description')
    raw_id_fields = ('vehicle', 'driver')


@admin.register(RouteStop)
class RouteStopAdmin(admin.ModelAdmin):
    list_display = ('route', 'name', 'order', 'pickup_time', 'dropoff_time', 'is_active')
    list_filter = ('is_active', 'route')
    search_fields = ('name', 'location_note', 'route__name', 'route__code')
    ordering = ('route', 'order')


@admin.register(StudentTransportAssignment)
class StudentTransportAssignmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'route', 'stop', 'service_type', 'start_date', 'end_date', 'is_active')
    list_filter = ('service_type', 'is_active', 'route')
    search_fields = ('student__first_name', 'student__last_name', 'student__student_id', 'route__code')
    raw_id_fields = ('student', 'route', 'stop')
    date_hierarchy = 'start_date'


@admin.register(RouteSchedule)
class RouteScheduleAdmin(admin.ModelAdmin):
    list_display = ('route', 'day_of_week', 'start_time', 'is_active')
    list_filter = ('day_of_week', 'is_active')
    search_fields = ('route__name', 'route__code')


@admin.register(VehicleTracking)
class VehicleTrackingAdmin(admin.ModelAdmin):
    list_display = ('vehicle', 'route', 'latitude', 'longitude', 'speed', 'is_moving', 'timestamp')
    list_filter = ('is_moving', 'vehicle')
    search_fields = ('vehicle__plate_number', 'vehicle__name')
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)


@admin.register(ParentNotification)
class ParentNotificationAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'notification_type', 'sent_at', 'is_read')
    list_filter = ('notification_type', 'is_read')
    search_fields = ('assignment__student__first_name', 'assignment__student__last_name', 'message')
    date_hierarchy = 'sent_at'
    ordering = ('-sent_at',)
