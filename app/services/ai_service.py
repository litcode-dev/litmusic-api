import asyncio
import httpx
from app.config import get_settings
from app.models.ai_generation import AIProvider
from app.exceptions import AppError


async def _call_suno(prompt: str, style_prompt: str | None) -> bytes:
    """Call Suno API: submit generation, poll until complete, return audio bytes (MP3)."""
    settings = get_settings()
    if not settings.suno_api_key:
        raise AppError("Suno API key not configured", status_code=503)

    headers = {"Authorization": f"Bearer {settings.suno_api_key}"}
    payload = {"prompt": prompt, "make_instrumental": True, "wait_audio": False}
    if style_prompt:
        payload["tags"] = style_prompt

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{settings.suno_api_url}/api/generate",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        clips = resp.json()

    clip_id = clips[0]["id"]
    audio_url: str | None = None

    for _ in range(60):  # poll up to 5 minutes (60 × 5s)
        await asyncio.sleep(5)
        async with httpx.AsyncClient(timeout=15.0) as client:
            poll = await client.get(
                f"{settings.suno_api_url}/api/get?ids={clip_id}",
                headers=headers,
            )
            poll.raise_for_status()
            items = poll.json()

        clip = items[0]
        if clip.get("status") == "streaming":
            audio_url = clip["audio_url"]
            break
        if clip.get("status") in ("error", "failed"):
            raise AppError(f"Suno generation failed: {clip.get('error', 'unknown')}")

    if not audio_url:
        raise AppError("Suno generation timed out after 5 minutes")

    async with httpx.AsyncClient(timeout=60.0) as client:
        audio_resp = await client.get(audio_url)
        audio_resp.raise_for_status()
        return audio_resp.content


async def _call_self_hosted(prompt: str, style_prompt: str | None) -> bytes:
    """Call self-hosted generation API. Expects POST /generate returning audio bytes (WAV)."""
    settings = get_settings()
    if not settings.ai_selfhosted_url:
        raise AppError("Self-hosted AI URL not configured", status_code=503)

    headers = {}
    if settings.ai_selfhosted_api_key:
        headers["Authorization"] = f"Bearer {settings.ai_selfhosted_api_key}"

    payload: dict = {"prompt": prompt}
    if style_prompt:
        payload["style"] = style_prompt

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.ai_selfhosted_url}/generate",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.content


async def generate_audio(
    provider: AIProvider, prompt: str, style_prompt: str | None
) -> bytes:
    """Dispatch to the correct AI provider. Returns raw audio bytes."""
    if provider == AIProvider.suno:
        return await _call_suno(prompt, style_prompt)
    if provider == AIProvider.self_hosted:
        return await _call_self_hosted(prompt, style_prompt)
    raise AppError(f"Unknown AI provider: {provider}", status_code=400)
