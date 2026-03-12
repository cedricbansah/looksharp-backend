from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("offers", "0007_remove_offer_points_required"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="redemption",
            name="points_spent",
        ),
    ]
