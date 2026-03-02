from django.db import models


class Period(models.Model):
    name = models.CharField(max_length=64)
    order = models.PositiveSmallIntegerField(default=1)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("order", "name")
        unique_together = ("order", "name")

    def __str__(self) -> str:
        return self.name


class Room(models.Model):
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32, blank=True)
    capacity = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        unique_together = ("name", "code")

    def __str__(self) -> str:
        return f"{self.code} - {self.name}" if self.code else self.name


class TimetableEntry(models.Model):
    MON = "MON"
    TUE = "TUE"
    WED = "WED"
    THU = "THU"
    FRI = "FRI"
    SAT = "SAT"
    SUN = "SUN"

    WEEKDAY_CHOICES = (
        (MON, "Monday"),
        (TUE, "Tuesday"),
        (WED, "Wednesday"),
        (THU, "Thursday"),
        (FRI, "Friday"),
        (SAT, "Saturday"),
        (SUN, "Sunday"),
    )

    offering = models.ForeignKey("academics.CourseOffering", on_delete=models.CASCADE)
    weekday = models.CharField(max_length=3, choices=WEEKDAY_CHOICES)
    period = models.ForeignKey(Period, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("weekday", "period__order", "period__name")
        unique_together = (
            ("offering", "weekday", "period"),
        )

    def __str__(self) -> str:
        return f"{self.get_weekday_display()} - {self.period} - {self.offering}"
