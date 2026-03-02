import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services import oauth_service
from app.exceptions import UnauthorizedError


def test_get_google_auth_url_contains_required_params():
    state = "test-state-123"
    url = oauth_service.get_google_auth_url(state)
    assert "accounts.google.com" in url
    assert "state=test-state-123" in url
    assert "response_type=code" in url
    assert "scope=" in url


@pytest.mark.asyncio
async def test_exchange_google_code_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "ya29.test-token",
        "token_type": "Bearer",
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client):
        result = await oauth_service.exchange_google_code("auth-code-xyz")

    assert result["access_token"] == "ya29.test-token"
    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args
    assert oauth_service.GOOGLE_TOKEN_URL in call_kwargs.args or \
        oauth_service.GOOGLE_TOKEN_URL == call_kwargs.args[0]


@pytest.mark.asyncio
async def test_exchange_google_code_failure_raises():
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"error": "invalid_grant"}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(UnauthorizedError, match="Failed to exchange Google authorization code"):
            await oauth_service.exchange_google_code("bad-code")


@pytest.mark.asyncio
async def test_get_google_user_info_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "sub": "google-uid-12345",
        "email": "user@example.com",
        "name": "Test User",
        "picture": "https://lh3.googleusercontent.com/photo.jpg",
    }

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client):
        result = await oauth_service.get_google_user_info("ya29.test-token")

    assert result["sub"] == "google-uid-12345"
    assert result["email"] == "user@example.com"
    mock_client.get.assert_called_once()
    call_args = mock_client.get.call_args
    assert "Authorization" in call_args.kwargs.get("headers", {})


@pytest.mark.asyncio
async def test_get_google_user_info_failure_raises():
    mock_response = MagicMock()
    mock_response.status_code = 401

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("app.services.oauth_service.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(UnauthorizedError, match="Failed to fetch Google user info"):
            await oauth_service.get_google_user_info("expired-token")
