import httpx
from app.config import get_settings
from app.exceptions import PaymentError


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
    base_url = settings.flutterwave_base_url
    secret_key = settings.flutterwave_secret_key or settings.flw_secret_key
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
            f"{base_url}/payments",
            json=payload,
            headers={"Authorization": f"Bearer {secret_key}"},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
    if data.get("status") != "success":
        raise PaymentError(data.get("message", "Flutterwave initialization failed"))
    return {"payment_link": data["data"]["link"], "tx_ref": tx_ref}


def verify_webhook_signature(verif_hash: str) -> bool:
    """Verify Flutterwave webhook by comparing verif-hash header to configured secret hash."""
    settings = get_settings()
    expected = settings.flutterwave_secret_hash or settings.flw_hash
    return verif_hash == expected


async def verify_transaction(transaction_id: str) -> dict:
    """Verify a Flutterwave transaction by ID. Returns the full API response dict."""
    settings = get_settings()
    base_url = settings.flutterwave_base_url
    secret_key = settings.flutterwave_secret_key or settings.flw_secret_key
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{base_url}/transactions/{transaction_id}/verify",
            headers={"Authorization": f"Bearer {secret_key}"},
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json()
