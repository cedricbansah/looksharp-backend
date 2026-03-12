from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("offers", "0006_sync_offer_codes_from_client"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="offer",
            name="points_required",
        ),
    ]
