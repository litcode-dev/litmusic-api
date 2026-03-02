import httpx
from app.config import get_settings
from app.exceptions import PaymentError

FLW_BASE = "https://api.flutterwave.com/v3"


async def initialize_payment(
    amount: float,
    email: str,
    name: str,
    product_name: str,
    metadata: dict,
    tx_ref: str,
) -> dict:
    """Initialize a Flutterwave payment. Returns {payment_link, tx_ref}."""
    settings = get_settings()
    payload = {
        "tx_ref": tx_ref,
        "amount": str(amount),
        "currency": "USD",
        "redirect_url": f"{settings.frontend_url}/payments/callback",
        "customer": {"email": email, "name": name},
        "meta": metadata,
        "customizations": {"title": product_name},
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{FLW_BASE}/payments",
            json=payload,
            headers={"Authorization": f"Bearer {settings.flw_secret_key}"},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
    if data.get("status") != "success":
        raise PaymentError(data.get("message", "Flutterwave initialization failed"))
    return {"payment_link": data["data"]["link"], "tx_ref": tx_ref}


def verify_webhook_signature(verif_hash: str) -> bool:
    """Verify Flutterwave webhook by comparing verif-hash header to configured FLW_HASH."""
    settings = get_settings()
    return verif_hash == settings.flw_hash


async def verify_transaction(transaction_id: str) -> dict:
    """Verify a Flutterwave transaction by ID. Returns the full API response dict."""
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{FLW_BASE}/transactions/{transaction_id}/verify",
            headers={"Authorization": f"Bearer {settings.flw_secret_key}"},
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json()
