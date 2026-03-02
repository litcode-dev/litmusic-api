import httpx
from app.config import get_settings

settings = get_settings()
ONESIGNAL_API_URL = "https://onesignal.com/api/v1/notifications"


async def send_notification(
    player_id: str,
    title: str,
    message: str,
    data: dict | None = None,
) -> bool:
    """Send a push notification to a single device. Returns True on success."""
    payload = {
        "app_id": settings.onesignal_app_id,
        "include_player_ids": [player_id],
        "headings": {"en": title},
        "contents": {"en": message},
        "data": data or {},
    }
    headers = {
        "Authorization": f"Basic {settings.onesignal_api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(ONESIGNAL_API_URL, json=payload, headers=headers)
        return response.status_code == 200


async def send_purchase_confirmation_notification(player_id: str, loop_title: str) -> bool:
    return await send_notification(
        player_id=player_id,
        title="Purchase Successful!",
        message=f'You now own "{loop_title}". Download it anytime.',
        data={"type": "purchase_confirmation"},
    )


async def send_new_loop_notification(player_id: str, genre: str, loop_title: str, loop_id: str) -> bool:
    return await send_notification(
        player_id=player_id,
        title=f"New {genre} Loop!",
        message=f'"{loop_title}" just dropped. Check it out.',
        data={"type": "new_loop", "loop_id": loop_id},
    )
