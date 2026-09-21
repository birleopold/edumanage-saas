from rest_framework import serializers

from apps.tenant.attendance.models import AttendanceEntry
from apps.tenant.parents.models import ParentProfile
from apps.tenant.students.models import StudentProfile
from apps.tenant.teachers.models import TeacherProfile


class StudentSummarySerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    campus = serializers.SerializerMethodField()
    stream = serializers.SerializerMethodField()
    class_group = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = ("id", "student_id", "name", "email", "campus", "stream", "class_group")
        read_only_fields = fields

    def get_name(self, obj):
        return obj.get_full_name()

    def get_campus(self, obj):
        return str(obj.campus or "")

    def get_stream(self, obj):
        return str(obj.stream or "")

    def get_class_group(self, obj):
        return str(obj.stream.class_group) if obj.stream_id else ""


class TeacherSummarySerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    campus = serializers.SerializerMethodField()

    class Meta:
        model = TeacherProfile
        fields = ("id", "staff_id", "name", "phone", "email", "campus")
        read_only_fields = fields

    def get_name(self, obj):
        return str(obj)

    def get_campus(self, obj):
        return str(obj.campus or "")


class TeacherDirectorySerializer(TeacherSummarySerializer):
    """Non-sensitive staff directory fields for peer teachers."""

    class Meta(TeacherSummarySerializer.Meta):
        fields = ("id", "staff_id", "name", "campus")
        read_only_fields = fields


class ParentSummarySerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = ParentProfile
        fields = (
            "id",
            "name",
            "phone",
            "email",
            "allow_sms_alerts",
            "allow_whatsapp_alerts",
        )
        read_only_fields = fields

    def get_name(self, obj):
        return str(obj)


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
