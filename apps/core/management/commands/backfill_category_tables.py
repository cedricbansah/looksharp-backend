from django.core.management.base import BaseCommand

from apps.core.firestore_migration import env_default, initialize_firestore
from apps.offers.models import OfferCategory
from apps.surveys.models import SurveyCategory


class Command(BaseCommand):
    help = "Backfill survey_categories and offer_categories from Firestore into Postgres."

    def add_arguments(self, parser):
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Update existing category rows if they already exist.",
        )
        parser.add_argument(
            "--service-account-path",
            default=env_default("FIREBASE_SERVICE_ACCOUNT_KEY_PATH"),
            help="Path to Firebase service account JSON.",
        )
        parser.add_argument(
            "--service-account-json",
            default=env_default("FIREBASE_SERVICE_ACCOUNT_JSON"),
            help="Inline Firebase service account JSON.",
        )
        parser.add_argument(
            "--project-id",
            default=env_default("FIREBASE_PROJECT_ID"),
            help="Optional Firestore project id override.",
        )

    def handle(self, *args, **options):
        firestore_client = initialize_firestore(
            service_account_path=options["service_account_path"],
            service_account_json=options["service_account_json"],
            project_id=options["project_id"],
        )

        survey_loaded = self._sync_collection(
            firestore_client=firestore_client,
            collection_name="survey_categories",
            model=SurveyCategory,
            overwrite=options["overwrite"],
        )
        offer_loaded = self._sync_collection(
            firestore_client=firestore_client,
            collection_name="offer_categories",
            model=OfferCategory,
            overwrite=options["overwrite"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfilled categories: survey_categories={survey_loaded}, offer_categories={offer_loaded}"
            )
        )

    def _sync_collection(self, *, firestore_client, collection_name, model, overwrite):
        loaded = 0
        for snapshot in firestore_client.collection(collection_name).stream():
            document = snapshot.to_dict() or {}
            defaults = {
                "name": document.get("name", ""),
                "icon": document.get("icon", ""),
            }
            if overwrite:
                model.objects.update_or_create(id=snapshot.id, defaults=defaults)
                loaded += 1
                continue

            _, created = model.objects.get_or_create(id=snapshot.id, defaults=defaults)
            if created:
                loaded += 1
        return loaded
