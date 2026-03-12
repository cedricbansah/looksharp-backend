from django.db import migrations


def _sync_offer_codes_from_client(apps, schema_editor):
    Offer = apps.get_model("offers", "Offer")

    updates = []
    for offer in Offer.objects.select_related("client").iterator():
        client = offer.client
        expected_code = (client.client_code or "") if client else ""
        if (offer.offer_code or "") == expected_code:
            continue
        offer.offer_code = expected_code
        updates.append(offer)

    if updates:
        Offer.objects.bulk_update(updates, ["offer_code"])


class Migration(migrations.Migration):
    dependencies = [
        ("offers", "0005_offer_client_fk"),
    ]

    operations = [
        migrations.RunPython(_sync_offer_codes_from_client, migrations.RunPython.noop),
    ]
