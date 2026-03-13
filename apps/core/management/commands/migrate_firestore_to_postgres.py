from __future__ import annotations

import logging

from django.core.management.base import BaseCommand, CommandError

from apps.core.firestore_migration import default_config_path, env_default, run_migration


class Command(BaseCommand):
    help = "Migrate Firestore collections/documents into PostgreSQL tables."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--config",
            default=str(default_config_path()),
            help="Path to JSON config file with source/target mappings.",
        )
        parser.add_argument(
            "--database-url",
            default=env_default("DATABASE_URL"),
            help="Postgres connection URL (defaults to DATABASE_URL env var).",
        )
        parser.add_argument(
            "--service-account",
            default=env_default("FIREBASE_SERVICE_ACCOUNT_KEY_PATH"),
            help=(
                "Path to Firebase service account JSON. If omitted, "
                "Application Default Credentials are used."
            ),
        )
        parser.add_argument(
            "--service-account-json",
            default=env_default("FIREBASE_SERVICE_ACCOUNT_JSON"),
            help=(
                "Firebase service account payload as raw JSON or base64-encoded JSON. "
                "Defaults to FIREBASE_SERVICE_ACCOUNT_JSON env var."
            ),
        )
        parser.add_argument(
            "--project-id",
            default=env_default("FIREBASE_PROJECT_ID"),
            help="Optional Firebase project ID override.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=None,
            help="Rows per upsert batch. Defaults to config batch_size or 500.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Transform and validate rows without writing to PostgreSQL.",
        )
        parser.add_argument(
            "--log-level",
            default="INFO",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            help="Log verbosity.",
        )

    def handle(self, *args, **options) -> None:
        logging.basicConfig(
            level=getattr(logging, options["log_level"]),
            format="%(asctime)s %(levelname)s %(message)s",
            force=True,
        )

        try:
            summary = run_migration(
                config_path=options["config"],
                database_url=options["database_url"],
                service_account_path=options["service_account"],
                service_account_json=options["service_account_json"],
                project_id=options["project_id"],
                batch_size_override=options["batch_size"],
                dry_run=options["dry_run"],
            )
        except Exception as exc:  # noqa: BLE001
            raise CommandError(str(exc)) from exc

        totals = summary["totals"]
        self.stdout.write(
            self.style.SUCCESS(
                "Migration finished "
                f"(dry_run={summary['dry_run']}, batch_size={summary['batch_size']}, "
                f"elapsed={summary['elapsed']}s)."
            )
        )
        self.stdout.write(
            f"Totals: processed={totals['processed']} loaded={totals['loaded']} skipped={totals['skipped']}"
        )

        for item in summary["results"]:
            self.stdout.write(
                f"- {item['mapping']}: processed={item['processed']} "
                f"loaded={item['loaded']} skipped={item['skipped']}"
            )
            if item["skip_reasons"]:
                self.stdout.write(f"  skip_reasons={item['skip_reasons']}")
