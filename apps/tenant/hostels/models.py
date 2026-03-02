from django.db import models


class Hostel(models.Model):
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)
        unique_together = ("name", "code")

    def __str__(self) -> str:
        return f"{self.code} - {self.name}" if self.code else self.name


class HostelRoom(models.Model):
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name="rooms")
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32, blank=True)
    capacity = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("hostel__name", "name")
        unique_together = ("hostel", "name", "code")

    def __str__(self) -> str:
        return f"{self.hostel} - {self.name}" if self.name else str(self.hostel)


class Bed(models.Model):
    room = models.ForeignKey(HostelRoom, on_delete=models.CASCADE, related_name="beds")
    label = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("room__hostel__name", "room__name", "label")
        unique_together = ("room", "label")

    def __str__(self) -> str:
        return f"{self.room} - {self.label}"


class BedAllocation(models.Model):
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"

    STATUS_CHOICES = (
        (ACTIVE, "Active"),
        (ENDED, "Ended"),
    )

    bed = models.ForeignKey(Bed, on_delete=models.CASCADE)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.CASCADE)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=ACTIVE)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["bed"],
                condition=models.Q(status="ACTIVE"),
                name="uniq_active_bed_allocation",
            )
        ]

    def __str__(self) -> str:
        return f"{self.student} -> {self.bed}"
