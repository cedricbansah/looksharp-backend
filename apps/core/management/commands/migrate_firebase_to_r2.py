"""Management command to migrate Firebase Storage files to Cloudflare R2.

For each model/field with a Firebase Storage URL:
1. Download the file (plain HTTP first; falls back to Firebase Admin SDK for private files)
2. Detect content type from magic bytes
3. Upload to R2 via services.r2.upload_file
4. Update the DB record with the new R2 URL

Usage:
    python manage.py migrate_firebase_to_r2 --dry-run
    python manage.py migrate_firebase_to_r2
    python manage.py migrate_firebase_to_r2 --model Client
"""

from __future__ import annotations

import io
import logging
import urllib.parse

import requests
from django.core.management.base import BaseCommand

from services.r2 import upload_file

logger = logging.getLogger(__name__)

FIREBASE_URL_FRAGMENTS = ("firebasestorage.googleapis.com", "storage.googleapis.com")

# (model_import_path, field_name, r2_key_template)
# r2_key_template uses {id} as the object pk placeholder.
MIGRATIONS = [
    ("apps.clients.models", "Client", "logo_url", "clients/{id}/logo"),
    ("apps.offers.models", "Offer", "poster_url", "offers/{id}/poster"),
    ("apps.users.models", "User", "profile_photo_url", "users/{id}/profile_photo"),
    ("apps.verifications.models", "Verification", "id_front_url", "verifications/{id}/id_front"),
    ("apps.verifications.models", "Verification", "id_back_url", "verifications/{id}/id_back"),
    ("apps.verifications.models", "Verification", "selfie_url", "verifications/{id}/selfie"),
]


def _is_firebase_url(url: str) -> bool:
    return any(frag in url for frag in FIREBASE_URL_FRAGMENTS)


def _detected_content_type(data: bytes) -> str | None:
    header = data[:12]
    if header[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if header[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    return None


def _download_public(url: str) -> bytes | None:
    """Try downloading url with a plain HTTP GET. Returns None on auth errors."""
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code in (401, 403):
            return None
        resp.raise_for_status()
        return resp.content
    except requests.RequestException as exc:
        raise RuntimeError(f"HTTP download failed: {exc}") from exc


def _parse_firebase_url(url: str) -> tuple[str, str] | None:
    """
    Extract (bucket, blob_path) from a Firebase Storage URL.

    Supported formats:
      https://firebasestorage.googleapis.com/v0/b/{bucket}/o/{encoded_path}?...
      https://storage.googleapis.com/{bucket}/{path}
    """
    parsed = urllib.parse.urlparse(url)
    if "firebasestorage.googleapis.com" in parsed.netloc:
        # path: /v0/b/{bucket}/o/{encoded_path}
        parts = parsed.path.split("/")
        try:
            b_idx = parts.index("b")
            o_idx = parts.index("o")
            bucket = parts[b_idx + 1]
            blob_path = urllib.parse.unquote("/".join(parts[o_idx + 1 :]))
            return bucket, blob_path
        except (ValueError, IndexError):
            return None
    if "storage.googleapis.com" in parsed.netloc:
        # path: /{bucket}/{blob_path}
        path_parts = parsed.path.lstrip("/").split("/", 1)
        if len(path_parts) == 2:
            return path_parts[0], path_parts[1]
    return None


def _download_via_firebase_admin(url: str) -> bytes:
    """Download a private Firebase Storage file using the Admin SDK."""
    import firebase_admin
    from firebase_admin import storage as fb_storage

    parsed = _parse_firebase_url(url)
    if parsed is None:
        raise RuntimeError(f"Cannot parse Firebase URL: {url}")
    bucket_name, blob_path = parsed

    # Ensure the app is initialised (it may already be from auth middleware).
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app()

    bucket = fb_storage.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    return blob.download_as_bytes()


def _download(url: str) -> bytes:
    data = _download_public(url)
    if data is None:
        logger.debug("Public download denied, trying Firebase Admin SDK for %s", url)
        data = _download_via_firebase_admin(url)
    return data


def _import_model(module_path: str, model_name: str):
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, model_name)


class Command(BaseCommand):
    help = "Migrate Firebase Storage file URLs to Cloudflare R2."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be migrated without downloading or uploading anything.",
        )
        parser.add_argument(
            "--model",
            default=None,
            help="Limit migration to a specific model name (e.g. Client, Offer, User, Verification).",
        )

    def handle(self, *args, **options) -> None:
        dry_run: bool = options["dry_run"]
        model_filter: str | None = options["model"]

        total_found = 0
        total_migrated = 0
        total_failed = 0
        total_skipped = 0

        for module_path, model_name, field_name, key_template in MIGRATIONS:
            if model_filter and model_filter.lower() != model_name.lower():
                continue

            model = _import_model(module_path, model_name)
            filter_q = {f"{field_name}__contains": "googleapis.com"}
            qs = model.objects.filter(**filter_q)
            count = qs.count()

            if count == 0:
                self.stdout.write(f"{model_name}.{field_name}: no Firebase URLs found, skipping.")
                continue

            self.stdout.write(
                self.style.WARNING(
                    f"{model_name}.{field_name}: {count} Firebase URL(s) found."
                )
            )
            total_found += count

            if dry_run:
                for obj in qs.iterator():
                    url = getattr(obj, field_name)
                    self.stdout.write(f"  [dry-run] would migrate pk={obj.pk}: {url}")
                total_skipped += count
                continue

            for obj in qs.iterator():
                url = getattr(obj, field_name)
                if not _is_firebase_url(url):
                    total_skipped += 1
                    continue

                r2_key = key_template.format(id=obj.pk)
                try:
                    data = _download(url)
                    content_type = _detected_content_type(data)
                    if content_type is None:
                        # Fall back to octet-stream rather than failing outright.
                        content_type = "application/octet-stream"
                        logger.warning(
                            "Unknown content type for %s pk=%s, using application/octet-stream",
                            model_name,
                            obj.pk,
                        )
                    new_url = upload_file(io.BytesIO(data), r2_key, content_type)
                    setattr(obj, field_name, new_url)
                    obj.save(update_fields=[field_name])
                    self.stdout.write(
                        self.style.SUCCESS(f"  Migrated {model_name} pk={obj.pk}: {new_url}")
                    )
                    total_migrated += 1
                except Exception as exc:  # noqa: BLE001
                    self.stderr.write(
                        self.style.ERROR(
                            f"  FAILED {model_name} pk={obj.pk} field={field_name}: {exc}"
                        )
                    )
                    total_failed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. found={total_found} migrated={total_migrated} "
                f"failed={total_failed} skipped={total_skipped} dry_run={dry_run}"
            )
        )
