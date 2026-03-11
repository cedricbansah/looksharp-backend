from django.db import migrations, models
import django.db.models.deletion


def _backfill_offer_client_fk(apps, schema_editor):
    Offer = apps.get_model("offers", "Offer")
    Client = apps.get_model("clients", "Client")

    client_ids = set(Client.objects.values_list("id", flat=True))
    updates = []
    for offer in Offer.objects.exclude(client_legacy_id=""):
        legacy_id = offer.client_legacy_id
        if legacy_id and legacy_id in client_ids:
            offer.client_id = legacy_id
            updates.append(offer)

    if updates:
        Offer.objects.bulk_update(updates, ["client"])


def _restore_offer_legacy_client_id(apps, schema_editor):
    Offer = apps.get_model("offers", "Offer")

    updates = []
    for offer in Offer.objects.exclude(client_id__isnull=True):
        offer.client_legacy_id = offer.client_id
        updates.append(offer)

    if updates:
        Offer.objects.bulk_update(updates, ["client_legacy_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0003_alter_client_logo_url_alter_client_website_url"),
        ("offers", "0004_remove_offer_offers_is_dele_15d9e5_idx_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="offer",
            old_name="client_id",
            new_name="client_legacy_id",
        ),
        migrations.AddField(
            model_name="offer",
            name="client",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="offers",
                to="clients.client",
            ),
        ),
        migrations.RunPython(_backfill_offer_client_fk, _restore_offer_legacy_client_id),
        migrations.RemoveField(
            model_name="offer",
            name="client_name",
        ),
        migrations.RemoveField(
            model_name="offer",
            name="client_logo_url",
        ),
        migrations.RemoveField(
            model_name="offer",
            name="client_legacy_id",
        ),
    ]
