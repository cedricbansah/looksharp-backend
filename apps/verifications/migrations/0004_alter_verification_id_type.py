from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "verifications",
            "0003_alter_verification_id_back_url_and_more",
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="verification",
            name="id_type",
            field=models.CharField(
                choices=[
                    ("ghana_card", "Ghana Card"),
                    ("passport", "Passport"),
                    ("voter_id", "Voter ID"),
                    ("drivers_license", "Driver's License"),
                ],
                max_length=32,
            ),
        ),
    ]
