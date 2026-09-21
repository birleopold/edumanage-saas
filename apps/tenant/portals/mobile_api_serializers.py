from rest_framework import serializers

from apps.tenant.attendance.models import AttendanceEntry


class AttendanceEntryWriteSerializer(serializers.Serializer):
    student_id = serializers.IntegerField(min_value=1)
    status = serializers.ChoiceField(
        choices=AttendanceEntry.STATUS_CHOICES,
        default=AttendanceEntry.PRESENT,
    )
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class AttendanceMarkSerializer(serializers.Serializer):
    date = serializers.DateField(required=False)
    entries = AttendanceEntryWriteSerializer(many=True, allow_empty=False)

    def validate_entries(self, entries):
        student_ids = [row["student_id"] for row in entries]
        if len(student_ids) != len(set(student_ids)):
            raise serializers.ValidationError("Each student may appear only once.")
        return entries
