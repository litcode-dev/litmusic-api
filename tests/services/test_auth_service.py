import pytest
from app.services.auth_service import (
    hash_password, verify_password, create_access_token,
    decode_access_token, create_refresh_token
)
from app.exceptions import UnauthorizedError


@pytest.mark.asyncio
async def test_password_hash_and_verify():
    hashed = await hash_password("mysecret")
    assert await verify_password("mysecret", hashed)
    assert not await verify_password("wrong", hashed)


def test_access_token_encodes_user_info():
    token = create_access_token("user-123", "user")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "user"


def test_invalid_token_raises():
    with pytest.raises(UnauthorizedError):
        decode_access_token("not.a.valid.token")


def test_refresh_token_is_uuid_string():
    token = create_refresh_token()
    import uuid
    uuid.UUID(token)  # raises if not valid UUID


@pytest.mark.asyncio
async def test_different_passwords_do_not_match():
    hashed = await hash_password("password1")
    assert not await verify_password("password2", hashed)
