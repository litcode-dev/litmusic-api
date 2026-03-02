import pytest
from unittest.mock import AsyncMock, patch
from app.services.onesignal_service import send_notification


@pytest.mark.asyncio
async def test_send_notification_success():
    mock_response = AsyncMock()
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.services.onesignal_service.httpx.AsyncClient", return_value=mock_client):
        result = await send_notification("player-1", "Title", "Body")
    assert result is True


@pytest.mark.asyncio
async def test_send_notification_returns_false_on_error():
    mock_response = AsyncMock()
    mock_response.status_code = 400

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.services.onesignal_service.httpx.AsyncClient", return_value=mock_client):
        result = await send_notification("player-1", "Title", "Body")
    assert result is False
