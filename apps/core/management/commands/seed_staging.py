"""
Management command to seed staging data for verifications and withdrawals.

Usage:
    # Seed verifications only (recipient code not yet generated)
    python manage.py seed_staging <firebase_uid>

    # Seed verifications + withdrawals once a real recipient code exists
    python manage.py seed_staging <firebase_uid> --recipient-code RCP_xxxxxxxxxxxxxxxx

    # Re-run cleanly
    python manage.py seed_staging <firebase_uid> --recipient-code RCP_xxx --clear

Recipient codes are generated through the Paystack transfer recipient API and saved
to the user via the admin "Generate Recipient Code" action on a verification record.
Run this command without --recipient-code first, then generate the code through the
admin UI, then re-run with --recipient-code to seed withdrawals.
"""

import uuid

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.users.models import User
from apps.verifications.models import Verification
from apps.withdrawals.models import Withdrawal

PLACEHOLDER_URL = "https://placehold.co/600x400.png"


class Command(BaseCommand):
    help = "Seed staging data for verifications and withdrawals"

    def add_arguments(self, parser):
        parser.add_argument("firebase_uid", type=str, help="Firebase UID of the test user")
        parser.add_argument("--email", type=str, default="staging@looksharp.test")
        parser.add_argument("--points", type=int, default=5000)
        parser.add_argument(
            "--recipient-code",
            type=str,
            default=None,
            help=(
                "Real Paystack recipient code (RCP_xxx) — required to seed withdrawals. "
                "Generate this via the admin UI after reviewing a verification."
            ),
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing verifications and withdrawals for this user first",
        )

    def handle(self, *args, **options):
        uid = options["firebase_uid"]
        email = options["email"]
        points = options["points"]
        recipient_code = options["recipient_code"]

        # ── User ─────────────────────────────────────────────────────────────
        user, created = User.objects.get_or_create(
            id=uid,
            defaults={
                "email": email,
                "first_name": "Staging",
                "last_name": "User",
                "points": points,
                "is_verified": True,
                "recipient_code": recipient_code or "",
            },
        )
        if not created:
            update_fields = []
            if user.points < points:
                user.points = points
                update_fields.append("points")
            if not user.is_verified:
                user.is_verified = True
                update_fields.append("is_verified")
            if recipient_code and user.recipient_code != recipient_code:
                user.recipient_code = recipient_code
                update_fields.append("recipient_code")
            if update_fields:
                user.save(update_fields=update_fields)

        action = "Created" if created else "Found existing"
        self.stdout.write(f"{action} user: {uid} ({user.email})")

        if options["clear"]:
            v_count, _ = Verification.objects.filter(user_id=uid).delete()
            w_count, _ = Withdrawal.objects.filter(user_id=uid).delete()
            self.stdout.write(f"Cleared {v_count} verification(s) and {w_count} withdrawal(s)")

        # ── Verifications ────────────────────────────────────────────────────
        verifications = [
            Verification(
                user_id=uid,
                full_name="Kwame Mensah",
                gender="male",
                nationality="Ghanaian",
                mobile_number="0241234567",
                network_provider="MTN",
                id_type="ghana_card",
                id_number="GHA-123456789-0",
                id_front_url=PLACEHOLDER_URL,
                id_back_url=PLACEHOLDER_URL,
                selfie_url=PLACEHOLDER_URL,
                status="pending",
                submitted_at=timezone.now(),
            ),
            Verification(
                user_id=uid,
                full_name="Ama Asante",
                gender="female",
                nationality="Ghanaian",
                mobile_number="0551234567",
                network_provider="Telecel",
                id_type="passport",
                id_number="G1234567",
                id_front_url=PLACEHOLDER_URL,
                id_back_url=PLACEHOLDER_URL,
                selfie_url=PLACEHOLDER_URL,
                status="approved",
                reviewed_by=uid,
                reviewed_at=timezone.now(),
                submitted_at=timezone.now(),
            ),
            Verification(
                user_id=uid,
                full_name="Kofi Boateng",
                gender="male",
                nationality="Ghanaian",
                mobile_number="0271234567",
                network_provider="ATMoney",
                id_type="voter_id",
                id_number="VID-987654321",
                id_front_url=PLACEHOLDER_URL,
                id_back_url=PLACEHOLDER_URL,
                selfie_url=PLACEHOLDER_URL,
                status="rejected",
                rejection_reason="ID image is blurry and unreadable.",
                reviewed_by=uid,
                reviewed_at=timezone.now(),
                submitted_at=timezone.now(),
            ),
        ]
        created_verifications = Verification.objects.bulk_create(verifications)
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(created_verifications)} verification(s): pending, approved, rejected"
            )
        )

        # ── Withdrawals ──────────────────────────────────────────────────────
        if not recipient_code:
            self.stdout.write(
                self.style.WARNING(
                    "\nSkipped withdrawals — no --recipient-code provided.\n"
                    "Steps to seed withdrawals:\n"
                    "  1. Open the pending verification above in the admin UI\n"
                    "  2. Click 'Generate Recipient Code' to call Paystack and get RCP_xxx\n"
                    "  3. Re-run: python manage.py seed_staging "
                    f"{uid} --recipient-code RCP_xxx --clear"
                )
            )
            return

        withdrawals = [
            Withdrawal(
                user_id=uid,
                amount_ghs="50.00",
                points_converted=500,
                recipient_code=recipient_code,
                transfer_reference=f"wd_{uuid.uuid4().hex}",
                status="pending",
            ),
            Withdrawal(
                user_id=uid,
                amount_ghs="100.00",
                points_converted=1000,
                recipient_code=recipient_code,
                transfer_reference=f"wd_{uuid.uuid4().hex}",
                transfer_code="TRF_staging_processing_001",
                status="processing",
            ),
            Withdrawal(
                user_id=uid,
                amount_ghs="200.00",
                points_converted=2000,
                recipient_code=recipient_code,
                transfer_reference=f"wd_{uuid.uuid4().hex}",
                transfer_code="TRF_staging_completed_001",
                status="completed",
                completed_at=timezone.now(),
            ),
            Withdrawal(
                user_id=uid,
                amount_ghs="75.00",
                points_converted=750,
                recipient_code=recipient_code,
                transfer_reference=f"wd_{uuid.uuid4().hex}",
                status="failed",
                failure_reason="Recipient account not found.",
            ),
        ]
        created_withdrawals = Withdrawal.objects.bulk_create(withdrawals)
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(created_withdrawals)} withdrawal(s): pending, processing, completed, failed"
            )
        )

        self.stdout.write(self.style.SUCCESS("\nDone. Staging data seeded successfully."))
