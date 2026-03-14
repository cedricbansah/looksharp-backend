import base64
import json
import logging
import re
from collections.abc import Iterable

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

HUBTEL_SINGLE_SMS_URL = "https://sms.hubtel.com/v1/messages/send"
HUBTEL_BATCH_SMS_URL = "https://sms.hubtel.com/v1/messages/batch/simple/send"
HUBTEL_PHONE_RE = re.compile(r"^[1-9]\d{7,14}$")
HUBTEL_TIMEOUT = 30
HUBTEL_BATCH_SIZE = 500
HUBTEL_BULK_SMS_MAX_LENGTH = 160


def normalize_phone_number(phone: str) -> str:
    """Normalize stored app phone numbers to Hubtel's international digit format."""
    if not phone or not phone.strip():
        raise ValueError("phone number is required")

    raw = phone.strip()
    digits = re.sub(r"\D", "", raw)

    if digits.startswith("0") and len(digits) == 10:
        normalized = f"233{digits[1:]}"
    elif 8 <= len(digits) <= 15 and not digits.startswith("0"):
        normalized = digits
    else:
        raise ValueError(
            f"phone number must be international digits, E.164, or Ghana local format: {phone!r}"
        )

    if not HUBTEL_PHONE_RE.fullmatch(normalized):
        raise ValueError(f"phone number is not a valid international value: {phone!r}")

    return normalized


def _mask_phone_number(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 4:
        return "<redacted>"
    return f"...{digits[-4:]}"


def _response_detail(response: requests.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = response.text.strip() or "<empty response>"

    if isinstance(body, str):
        return body
    return json.dumps(body, sort_keys=True)


def _hubtel_headers() -> dict[str, str]:
    username = settings.HUBTEL_USERNAME
    password = settings.HUBTEL_PASSWORD
    if not username or not password:
        raise ValueError("HUBTEL_USERNAME and HUBTEL_PASSWORD are required")

    encoded_auth = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {
        "Content-Type": "application/json",
        "Authorization": f"Basic {encoded_auth}",
    }


def _truncate_bulk_content(message: str) -> str:
    if len(message) <= HUBTEL_BULK_SMS_MAX_LENGTH:
        return message
    return message[: HUBTEL_BULK_SMS_MAX_LENGTH - 3] + "..."


def _post_sms(url: str, payload: dict, recipient_label: str) -> dict:
    response = requests.post(
        url,
        headers=_hubtel_headers(),
        json=payload,
        timeout=HUBTEL_TIMEOUT,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = _response_detail(response)
        logger.error(
            "Hubtel SMS request failed: status=%s to=%s detail=%s",
            response.status_code,
            recipient_label,
            detail,
        )
        raise requests.HTTPError(
            f"{exc}. Hubtel response: {detail}",
            response=response,
            request=exc.request,
        ) from exc

    return response.json()


def send_sms(to: str, message: str) -> dict:
    """Send a single SMS via Hubtel. Raises requests.HTTPError on non-2xx."""
    normalized_to = normalize_phone_number(to)
    payload = {
        "From": settings.HUBTEL_SENDER_ID,
        "To": normalized_to,
        "Content": message,
    }
    return _post_sms(
        HUBTEL_SINGLE_SMS_URL,
        payload,
        _mask_phone_number(normalized_to),
    )


def send_bulk_sms(recipients: Iterable[str], message: str) -> dict:
    """Send a bulk SMS via Hubtel. Raises requests.HTTPError on non-2xx."""
    normalized_recipients = [normalize_phone_number(recipient) for recipient in recipients]
    if not normalized_recipients:
        raise ValueError("at least one recipient is required")
    content = _truncate_bulk_content(message)

    last_response = None
    for start in range(0, len(normalized_recipients), HUBTEL_BATCH_SIZE):
        batch = normalized_recipients[start : start + HUBTEL_BATCH_SIZE]
        payload = {
            "From": settings.HUBTEL_SENDER_ID,
            "Recipients": batch,
            "Content": content,
        }
        recipient_label = f"{len(batch)} recipients"
        last_response = _post_sms(HUBTEL_BATCH_SMS_URL, payload, recipient_label)
    return last_response
