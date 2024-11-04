# Generated by Django 5.0.9 on 2024-10-31 14:28

import django.contrib.postgres.indexes
from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("authentik_core", "0040_provider_invalidation_flow"),
        ("authentik_providers_oauth2", "0022_remove_accesstoken_session_id_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunSQL("DROP INDEX IF EXISTS authentik_p_token_f99422_idx;"),
        migrations.RunSQL("DROP INDEX IF EXISTS authentik_p_token_a1d921_idx;"),
        migrations.AddIndex(
            model_name="accesstoken",
            index=django.contrib.postgres.indexes.HashIndex(
                fields=["token"], name="authentik_p_token_e00883_hash"
            ),
        ),
        migrations.AddIndex(
            model_name="refreshtoken",
            index=django.contrib.postgres.indexes.HashIndex(
                fields=["token"], name="authentik_p_token_32e2b7_hash"
            ),
        ),
    ]
