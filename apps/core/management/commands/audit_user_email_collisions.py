import json
from collections import defaultdict
from datetime import date, datetime

from django.core.management.base import BaseCommand

from apps.core.firestore_migration import env_default, initialize_firestore
from apps.offers.models import Redemption
from apps.responses.models import Response
from apps.surveys.models import Survey
from apps.users.models import User
from apps.verifications.models import Verification
from apps.withdrawals.models import Withdrawal


def _normalize_email(value):
    if value is None:
        return None
    email = str(value).strip().lower()
    return email or None


def _serialize_timestamp(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _collect_firestore_users(firestore_client):
    by_email = defaultdict(list)

    for snapshot in firestore_client.collection("users").stream():
        document = snapshot.to_dict() or {}
        email = _normalize_email(document.get("email"))
        if not email:
            continue
        by_email[email].append(
            {
                "id": snapshot.id,
                "created_at": _serialize_timestamp(document.get("created_at")),
                "updated_at": _serialize_timestamp(document.get("updated_at")),
            }
        )

    return dict(by_email)


def _collect_postgres_users():
    by_email = defaultdict(list)

    for row in User.objects.all().values("id", "email", "created_at", "updated_at"):
        email = _normalize_email(row["email"])
        if not email:
            continue
        by_email[email].append(
            {
                "id": row["id"],
                "created_at": _serialize_timestamp(row["created_at"]),
                "updated_at": _serialize_timestamp(row["updated_at"]),
            }
        )

    return dict(by_email)


def _postgres_reference_counts(uid):
    return {
        "responses": Response.objects.filter(user_id=uid).count(),
        "verifications": Verification.objects.filter(user_id=uid).count(),
        "withdrawals": Withdrawal.objects.filter(user_id=uid).count(),
        "redemptions": Redemption.objects.filter(user_id=uid).count(),
        "surveys_created": Survey.objects.filter(created_by=uid).count(),
    }


def _build_collision_report(firestore_users, postgres_users, *, email_filter=None):
    normalized_filter = _normalize_email(email_filter)
    report = []

    for email in sorted(set(firestore_users) | set(postgres_users)):
        if normalized_filter and email != normalized_filter:
            continue

        firestore_entries = firestore_users.get(email, [])
        postgres_entries = postgres_users.get(email, [])
        unique_ids = sorted({entry["id"] for entry in firestore_entries + postgres_entries})

        if len(unique_ids) < 2:
            continue

        firestore_by_id = {entry["id"]: entry for entry in firestore_entries}
        postgres_by_id = {entry["id"]: entry for entry in postgres_entries}

        report.append(
            {
                "email": email,
                "uids": [
                    {
                        "id": uid,
                        "in_firestore": uid in firestore_by_id,
                        "in_postgres": uid in postgres_by_id,
                        "firestore": firestore_by_id.get(uid),
                        "postgres": postgres_by_id.get(uid),
                        "postgres_references": _postgres_reference_counts(uid),
                    }
                    for uid in unique_ids
                ],
            }
        )

    return report


class Command(BaseCommand):
    help = "Audit emails that map to multiple user IDs across Firestore and PostgreSQL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            default=None,
            help="Limit the report to a single email address.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output the report as JSON.",
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
        firestore_users = _collect_firestore_users(firestore_client)
        postgres_users = _collect_postgres_users()
        report = _build_collision_report(
            firestore_users,
            postgres_users,
            email_filter=options["email"],
        )

        if options["json"]:
            self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
            return

        if not report:
            if options["email"]:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"No cross-system email collisions found for {_normalize_email(options['email'])}."
                    )
                )
            else:
                self.stdout.write(self.style.SUCCESS("No cross-system email collisions found."))
            return

        self.stdout.write(
            self.style.WARNING(f"Found {len(report)} colliding email(s) across Firestore/PostgreSQL.")
        )
        for item in report:
            self.stdout.write("")
            self.stdout.write(f"Email: {item['email']}")
            for uid in item["uids"]:
                location = []
                if uid["in_firestore"]:
                    location.append("firestore")
                if uid["in_postgres"]:
                    location.append("postgres")
                self.stdout.write(f"  UID: {uid['id']} [{', '.join(location)}]")
                if uid["firestore"]:
                    self.stdout.write(
                        "    firestore: "
                        f"created_at={uid['firestore']['created_at']} "
                        f"updated_at={uid['firestore']['updated_at']}"
                    )
                if uid["postgres"]:
                    self.stdout.write(
                        "    postgres: "
                        f"created_at={uid['postgres']['created_at']} "
                        f"updated_at={uid['postgres']['updated_at']}"
                    )
                counts = uid["postgres_references"]
                self.stdout.write(
                    "    refs: "
                    f"responses={counts['responses']} "
                    f"verifications={counts['verifications']} "
                    f"withdrawals={counts['withdrawals']} "
                    f"redemptions={counts['redemptions']} "
                    f"surveys_created={counts['surveys_created']}"
                )
