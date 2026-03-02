import hashlib
import hmac
import httpx
from app.config import get_settings
from app.exceptions import PaymentError

PAYSTACK_BASE = "https://api.paystack.co"


async def initialize_payment(
    amount_kobo: int,
    email: str,
    reference: str,
    metadata: dict,
) -> dict:
    """Initialize a Paystack transaction. Returns {authorization_url, reference}."""
    settings = get_settings()
    payload = {
        "email": email,
        "amount": amount_kobo,
        "reference": reference,
        "metadata": metadata,
        "currency": "NGN",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{PAYSTACK_BASE}/transaction/initialize",
            json=payload,
            headers={"Authorization": f"Bearer {settings.paystack_secret_key}"},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
    if not data.get("status"):
        raise PaymentError(data.get("message", "Paystack initialization failed"))
    return {
        "authorization_url": data["data"]["authorization_url"],
        "reference": reference,
    }


def verify_webhook_signature(payload: bytes, x_paystack_signature: str) -> bool:
    """Verify Paystack webhook HMAC-SHA512 signature."""
    settings = get_settings()
    expected = hmac.new(
        settings.paystack_secret_key.encode(),
        payload,
        hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(expected, x_paystack_signature)


async def verify_transaction(reference: str) -> dict:
    """Verify a Paystack transaction by reference. Returns the full API response dict."""
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{PAYSTACK_BASE}/transaction/verify/{reference}",
            headers={"Authorization": f"Bearer {settings.paystack_secret_key}"},
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json()
