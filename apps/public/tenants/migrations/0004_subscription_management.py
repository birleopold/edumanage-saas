# Generated for EduManage SaaS subscription management.

from django.db import migrations, models
import django.db.models.deletion


def seed_default_plans(apps, schema_editor):
    SubscriptionPlan = apps.get_model("tenants", "SubscriptionPlan")
    defaults = [
        {
            "code": "starter",
            "name": "Starter",
            "description": "Entry package for small schools starting with core school records.",
            "monthly_price": "150000.00",
            "annual_price": "1500000.00",
            "trial_days": 14,
            "max_students": 300,
            "max_staff": 40,
            "max_campuses": 1,
            "max_storage_mb": 2048,
            "features": ["academics", "students", "teachers", "parents", "attendance", "announcements", "documents"],
            "sort_order": 1,
        },
        {
            "code": "standard",
            "name": "Standard",
            "description": "Recommended package for most schools with finance, reports, exams and communication.",
            "monthly_price": "300000.00",
            "annual_price": "3000000.00",
            "trial_days": 14,
            "max_students": 1200,
            "max_staff": 150,
            "max_campuses": 3,
            "max_storage_mb": 10240,
            "features": ["academics", "admissions", "attendance", "assessments", "announcements", "coursework", "students", "teachers", "parents", "finance", "documents", "timetable", "exams", "reports"],
            "sort_order": 2,
        },
        {
            "code": "enterprise",
            "name": "Enterprise",
            "description": "Full package for large or multi-campus schools needing all modules and higher limits.",
            "monthly_price": "650000.00",
            "annual_price": "6500000.00",
            "trial_days": 14,
            "max_students": 0,
            "max_staff": 0,
            "max_campuses": 0,
            "max_storage_mb": 0,
            "features": ["academics", "admissions", "attendance", "assessments", "announcements", "coursework", "students", "teachers", "parents", "finance", "library", "transport", "hostels", "inventory", "documents", "timetable", "exams", "reports", "messaging", "hr", "analytics", "audit"],
            "sort_order": 3,
        },
    ]
    for plan in defaults:
        SubscriptionPlan.objects.update_or_create(code=plan["code"], defaults=plan)


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0003_platformauditevent"),
    ]

    operations = [
        migrations.CreateModel(
            name="SubscriptionPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(choices=[("starter", "Starter"), ("standard", "Standard"), ("enterprise", "Enterprise"), ("custom", "Custom")], max_length=50, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True)),
                ("currency", models.CharField(default="UGX", max_length=8)),
                ("monthly_price", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("annual_price", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("default_billing_cycle", models.CharField(choices=[("monthly", "Monthly"), ("annual", "Annual")], default="monthly", max_length=16)),
                ("trial_days", models.PositiveIntegerField(default=14)),
                ("max_students", models.PositiveIntegerField(default=0, help_text="0 means unlimited")),
                ("max_staff", models.PositiveIntegerField(default=0, help_text="0 means unlimited")),
                ("max_campuses", models.PositiveIntegerField(default=0, help_text="0 means unlimited")),
                ("max_storage_mb", models.PositiveIntegerField(default=0, help_text="0 means unlimited")),
                ("features", models.JSONField(blank=True, default=list)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("sort_order", "monthly_price", "name")},
        ),
        migrations.CreateModel(
            name="TenantSubscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("trialing", "Trialing"), ("active", "Active"), ("past_due", "Past due"), ("suspended", "Suspended"), ("cancelled", "Cancelled"), ("expired", "Expired")], default="trialing", max_length=20)),
                ("billing_cycle", models.CharField(choices=[("monthly", "Monthly"), ("annual", "Annual")], default="monthly", max_length=16)),
                ("currency", models.CharField(default="UGX", max_length=8)),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("trial_start", models.DateField(blank=True, null=True)),
                ("trial_end", models.DateField(blank=True, null=True)),
                ("current_period_start", models.DateField(blank=True, null=True)),
                ("current_period_end", models.DateField(blank=True, null=True)),
                ("next_billing_date", models.DateField(blank=True, null=True)),
                ("payment_status", models.CharField(choices=[("unpaid", "Unpaid"), ("partial", "Partial"), ("paid", "Paid"), ("waived", "Waived")], default="unpaid", max_length=16)),
                ("payment_reference", models.CharField(blank=True, max_length=120)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="subscriptions", to="tenants.subscriptionplan")),
                ("tenant", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="subscription", to="tenants.tenant")),
            ],
            options={"ordering": ("-updated_at",)},
        ),
        migrations.CreateModel(
            name="SubscriptionInvoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("invoice_number", models.CharField(max_length=80, unique=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("currency", models.CharField(default="UGX", max_length=8)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("open", "Open"), ("paid", "Paid"), ("void", "Void"), ("overdue", "Overdue")], default="open", max_length=16)),
                ("issued_on", models.DateField()),
                ("due_on", models.DateField(blank=True, null=True)),
                ("paid_on", models.DateField(blank=True, null=True)),
                ("payment_reference", models.CharField(blank=True, max_length=120)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("subscription", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="invoices", to="tenants.tenantsubscription")),
            ],
            options={"ordering": ("-issued_on", "-id")},
        ),
        migrations.AddIndex(model_name="tenantsubscription", index=models.Index(fields=["status", "next_billing_date"], name="tenants_ten_status_5debb4_idx")),
        migrations.AddIndex(model_name="tenantsubscription", index=models.Index(fields=["payment_status", "next_billing_date"], name="tenants_ten_payment_191b13_idx")),
        migrations.AddIndex(model_name="subscriptioninvoice", index=models.Index(fields=["status", "due_on"], name="tenants_sub_status_582d29_idx")),
        migrations.AlterField(
            model_name="platformauditevent",
            name="action",
            field=models.CharField(choices=[("TENANT_CREATED", "Tenant created"), ("TENANT_STATUS_CHANGED", "Tenant status changed"), ("TENANT_SUSPENDED", "Tenant suspended"), ("TENANT_REACTIVATED", "Tenant reactivated"), ("DOMAIN_CREATED", "Domain created"), ("DOMAIN_UPDATED", "Domain updated"), ("DOMAIN_VERIFIED", "Domain verified"), ("DOMAIN_SSL_UPDATED", "Domain SSL updated"), ("SUBSCRIPTION_CREATED", "Subscription created"), ("SUBSCRIPTION_UPDATED", "Subscription updated"), ("SUBSCRIPTION_PAYMENT_RECORDED", "Subscription payment recorded")], db_index=True, max_length=40),
        ),
        migrations.RunPython(seed_default_plans, migrations.RunPython.noop),
    ]
