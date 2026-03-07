from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

limiter = Limiter(key_func=get_remote_address)


def _get_user_id_key(request: Request) -> str:
    """Key AI rate limits by user ID extracted from JWT, falling back to IP."""
    from app.services.auth_service import decode_access_token
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = decode_access_token(auth[7:])
            return f"user:{payload.get('sub', '')}"
        except Exception:
            pass
    return get_remote_address(request)


ai_limiter = Limiter(key_func=_get_user_id_key)
