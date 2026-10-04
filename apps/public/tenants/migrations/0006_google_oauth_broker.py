from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("tenants", "0005_rename_tenants_pla_action__6226d0_idx_tenants_pla_action_ea814b_idx_and_more")]

    operations = [
        migrations.CreateModel(
            name="GoogleOAuthTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("state_digest", models.CharField(db_index=True, max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("return_domain", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to="tenants.domain")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="google_oauth_transactions", to="tenants.tenant")),
            ],
            options={"indexes": [models.Index(fields=["expires_at", "used_at"], name="tenants_goo_expires_89f52d_idx")]},
        ),
        migrations.CreateModel(
            name="GoogleLoginHandoff",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_digest", models.CharField(db_index=True, max_length=64, unique=True)),
                ("google_subject", models.CharField(max_length=255)),
                ("verified_email", models.EmailField(max_length=254)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("return_domain", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to="tenants.domain")),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="google_login_handoffs", to="tenants.tenant")),
            ],
            options={"indexes": [models.Index(fields=["expires_at", "used_at"], name="tenants_goo_expires_79a3e1_idx")]},
        ),
    ]
