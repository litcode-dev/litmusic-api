import pytest
from unittest.mock import AsyncMock, patch
from app.services import ai_service
from app.models.ai_generation import AIProvider


@pytest.mark.asyncio
async def test_generate_audio_suno_calls_suno(monkeypatch):
    mock_bytes = b"fake-audio"
    monkeypatch.setattr(ai_service, "_call_suno", AsyncMock(return_value=mock_bytes))
    result = await ai_service.generate_audio(AIProvider.suno, "chill afrobeat", None)
    assert result == mock_bytes


@pytest.mark.asyncio
async def test_generate_audio_self_hosted_calls_self_hosted(monkeypatch):
    mock_bytes = b"fake-wav"
    monkeypatch.setattr(ai_service, "_call_self_hosted", AsyncMock(return_value=mock_bytes))
    result = await ai_service.generate_audio(AIProvider.self_hosted, "lo-fi trap", "dark")
    assert result == mock_bytes


@pytest.mark.asyncio
async def test_self_hosted_raises_when_url_not_configured():
    from app.exceptions import AppError
    with patch("app.services.ai_service.get_settings") as mock_settings:
        mock_settings.return_value.ai_selfhosted_url = ""
        with pytest.raises(AppError, match="not configured"):
            await ai_service._call_self_hosted("prompt", None)
