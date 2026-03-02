import asyncio
from app.tasks.celery_app import celery_app


@celery_app.task(name="notification_tasks.send_purchase_confirmation")
def send_purchase_confirmation(user_id: str, purchase_id: str):
    async def _run():
        from app.database import AsyncSessionLocal
        from app.models.user import User
        from app.models.purchase import Purchase
        from app.models.loop import Loop
        from app.models.stem_pack import StemPack
        from app.services.onesignal_service import send_purchase_confirmation_notification
        import uuid

        async with AsyncSessionLocal() as db:
            user = await db.get(User, uuid.UUID(user_id))
            purchase = await db.get(Purchase, uuid.UUID(purchase_id))
            if not user or not purchase or not user.onesignal_player_id:
                return
            if purchase.loop_id:
                product = await db.get(Loop, purchase.loop_id)
            else:
                product = await db.get(StemPack, purchase.stem_pack_id)
            if product:
                await send_purchase_confirmation_notification(
                    user.onesignal_player_id, product.title
                )
    asyncio.run(_run())


@celery_app.task(name="notification_tasks.send_new_loop_notification")
def send_new_loop_notification(loop_id: str):
    async def _run():
        from app.database import AsyncSessionLocal
        from app.models.loop import Loop
        from app.models.user import User
        from app.services.onesignal_service import send_new_loop_notification as _notify
        from sqlalchemy import select
        import uuid

        async with AsyncSessionLocal() as db:
            loop = await db.get(Loop, uuid.UUID(loop_id))
            if not loop:
                return
            users = await db.scalars(
                select(User).where(User.onesignal_player_id.is_not(None))
            )
            for user in users.all():
                await _notify(
                    user.onesignal_player_id,
                    loop.genre.value,
                    loop.title,
                    loop_id,
                )
    asyncio.run(_run())
