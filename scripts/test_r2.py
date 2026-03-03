"""
Smoke-test Cloudflare R2 connectivity.
Run: python scripts/test_r2.py
"""
import io
import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from django.conf import settings
from services.r2 import get_r2_client, upload_file

KEY = "test/smoke-test.txt"
CONTENT = b"LookSharp R2 smoke test OK"


def main():
    print(f"Account ID : {settings.CLOUDFLARE_ACCOUNT_ID}")
    print(f"Bucket     : {settings.R2_BUCKET_NAME}")
    print(f"Public URL : {settings.R2_PUBLIC_URL}")
    print()

    # 1. Upload a small text file
    print("Uploading test object...")
    url = upload_file(io.BytesIO(CONTENT), key=KEY, content_type="text/plain")
    print(f"  Uploaded → {url}")

    # 2. Verify it exists via head_object
    print("Verifying object exists in bucket...")
    client = get_r2_client()
    resp = client.head_object(Bucket=settings.R2_BUCKET_NAME, Key=KEY)
    print(f"  Content-Type : {resp['ContentType']}")
    print(f"  Content-Length: {resp['ContentLength']} bytes")

    # 3. Clean up
    print("Deleting test object...")
    client.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=KEY)
    print("  Deleted.")

    print()
    print("R2 smoke test PASSED.")


if __name__ == "__main__":
    main()
