from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("users", "0010_hash_password_setup_tokens")]

    operations = [
        migrations.CreateModel(
            name="FederatedIdentity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("GOOGLE", "Google")], max_length=16)),
                ("subject", models.CharField(max_length=255)),
                ("email", models.EmailField(max_length=254)),
                ("email_verified", models.BooleanField(default=False)),
                ("linked_at", models.DateTimeField(auto_now_add=True)),
                ("last_login_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="federated_identities", to="users.user")),
            ],
            options={
                "indexes": [models.Index(fields=["provider", "email"], name="users_feder_provide_bda59d_idx")],
                "constraints": [
                    models.UniqueConstraint(fields=("provider", "subject"), name="users_unique_federated_subject"),
                    models.UniqueConstraint(fields=("user", "provider"), name="users_unique_provider_per_user"),
                ],
            },
        ),
    ]
