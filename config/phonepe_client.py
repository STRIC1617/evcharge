"""PhonePe Payment Gateway (Standard Checkout / PG API) integration helpers.

Requires the following environment variables:
- PHONEPE_MERCHANT_ID
- PHONEPE_SALT_KEY
- PHONEPE_SALT_INDEX (defaults to "1")
- PHONEPE_ENV: "sandbox" (default) or "production"
- PHONEPE_REDIRECT_URL: page the user's browser is sent to after paying
  (this backend's callback route will decide the final redirect)
- PHONEPE_CALLBACK_URL: absolute URL of this backend's S2S webhook endpoint
"""
import base64
import hashlib
import json
import os
import uuid
from typing import Any, Optional

import httpx

SANDBOX_BASE_URL = "https://api-preprod.phonepe.com/apis/pg-sandbox"
PRODUCTION_BASE_URL = "https://api.phonepe.com/apis/hermes"

PAY_PATH = "/pg/v1/pay"
STATUS_PATH = "/pg/v1/status"


def _get_config() -> tuple[str, str, str, str]:
    merchant_id = os.getenv("PHONEPE_MERCHANT_ID", "")
    salt_key = os.getenv("PHONEPE_SALT_KEY", "")
    salt_index = os.getenv("PHONEPE_SALT_INDEX", "1")
    if not merchant_id or not salt_key:
        raise RuntimeError(
            "PHONEPE_MERCHANT_ID and PHONEPE_SALT_KEY must be configured to accept payments"
        )
    env = os.getenv("PHONEPE_ENV", "sandbox").lower()
    base_url = PRODUCTION_BASE_URL if env == "production" else SANDBOX_BASE_URL
    return merchant_id, salt_key, salt_index, base_url


def new_merchant_transaction_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def _checksum(payload_segment: str, path: str, salt_key: str, salt_index: str) -> str:
    digest = hashlib.sha256(f"{payload_segment}{path}{salt_key}".encode()).hexdigest()
    return f"{digest}###{salt_index}"


async def create_payment(
    amount_rupees: float,
    merchant_transaction_id: str,
    user_id: int,
    notes: Optional[dict[str, Any]] = None,
) -> dict:
    """Initiate a PhonePe payment and return the hosted checkout redirect info."""
    merchant_id, salt_key, salt_index, base_url = _get_config()
    redirect_url = os.getenv("PHONEPE_REDIRECT_URL", "")
    callback_url = os.getenv("PHONEPE_CALLBACK_URL", "")

    payload = {
        "merchantId": merchant_id,
        "merchantTransactionId": merchant_transaction_id,
        "merchantUserId": f"U{user_id}",
        "amount": int(round(amount_rupees * 100)),
        "redirectUrl": redirect_url,
        "redirectMode": "REDIRECT",
        "callbackUrl": callback_url,
        "paymentInstrument": {"type": "PAY_PAGE"},
    }
    if notes:
        payload["merchantOrderId"] = merchant_transaction_id

    encoded_payload = base64.b64encode(json.dumps(payload).encode()).decode()
    checksum = _checksum(encoded_payload, PAY_PATH, salt_key, salt_index)

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{base_url}{PAY_PATH}",
            json={"request": encoded_payload},
            headers={
                "Content-Type": "application/json",
                "X-VERIFY": checksum,
                "accept": "application/json",
            },
        )
    data = response.json()
    if response.status_code >= 400 or not data.get("success", False):
        raise RuntimeError(data.get("message", "Failed to initiate PhonePe payment"))
    return data


async def check_status(merchant_transaction_id: str) -> dict:
    """Poll PhonePe for the current status of a transaction."""
    merchant_id, salt_key, salt_index, base_url = _get_config()
    path = f"{STATUS_PATH}/{merchant_id}/{merchant_transaction_id}"
    checksum = _checksum("", path, salt_key, salt_index)

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{base_url}{path}",
            headers={
                "Content-Type": "application/json",
                "X-VERIFY": checksum,
                "X-MERCHANT-ID": merchant_id,
                "accept": "application/json",
            },
        )
    return response.json()


def verify_callback_signature(raw_body: bytes, x_verify_header: str) -> bool:
    """Verify the X-VERIFY header PhonePe sends on the server-to-server webhook."""
    _, salt_key, salt_index, _ = _get_config()
    try:
        body = json.loads(raw_body)
        encoded_response = body.get("response", "")
    except (ValueError, AttributeError):
        return False
    if not encoded_response or not x_verify_header:
        return False
    expected = _checksum(encoded_response, "", salt_key, salt_index)
    return expected == x_verify_header


def decode_callback_payload(raw_body: bytes) -> dict:
    body = json.loads(raw_body)
    encoded_response = body.get("response", "")
    return json.loads(base64.b64decode(encoded_response))
