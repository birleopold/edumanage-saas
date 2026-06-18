from django.contrib import admin

from .models import AuditEvent, BackupJob, ConsentRecord, DataRetentionPolicy, ExportPermission, LoginHistory, SuspiciousLoginAlert, UserTwoFactorSetting

admin.site.register(AuditEvent)
admin.site.register(LoginHistory)
admin.site.register(UserTwoFactorSetting)
admin.site.register(ExportPermission)
admin.site.register(DataRetentionPolicy)
admin.site.register(ConsentRecord)
admin.site.register(BackupJob)
admin.site.register(SuspiciousLoginAlert)
