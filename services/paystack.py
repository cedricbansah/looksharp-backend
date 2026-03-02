import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)
PAYSTACK_BASE = "https://api.paystack.co"


def _headers():
    return {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def _request(method, path, **kwargs):
    """Make a Paystack API call. Raises requests.HTTPError on non-2xx."""
    url = f"{PAYSTACK_BASE}{path}"
    response = requests.request(method, url, headers=_headers(), timeout=30, **kwargs)
    response.raise_for_status()
    return response.json()


def list_banks(type="mobile_money", currency="GHS"):
    return _request("GET", "/bank", params={"type": type, "currency": currency})


def create_transfer_recipient(
    name,
    account_number,
    bank_code,
    type="mobile_money",
    currency="GHS",
):
    return _request(
        "POST",
        "/transferrecipient",
        json={
            "type": type,
            "name": name,
            "account_number": account_number,
            "bank_code": bank_code,
            "currency": currency,
        },
    )


def initiate_transfer(recipient, amount_kobo, reference, reason="LookSharp cashout"):
    """amount_kobo: amount in kobo (pesewas for GHS). 1 GHS = 100 kobo."""
    return _request(
        "POST",
        "/transfer",
        json={
            "source": "balance",
            "recipient": recipient,
            "amount": amount_kobo,
            "reference": reference,
            "reason": reason,
        },
    )


def finalize_transfer(transfer_code):
    return _request(
        "POST",
        "/transfer/finalize_transfer",
        json={"transfer_code": transfer_code},
    )
