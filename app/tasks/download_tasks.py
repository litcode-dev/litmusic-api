import asyncio
from app.tasks.celery_app import celery_app


@celery_app.task(name="download_tasks.generate_waveform_task")
def generate_waveform_task(loop_id: str):
    async def _run():
        import uuid
        import boto3
        from app.database import AsyncSessionLocal
        from app.models.loop import Loop
        from app.services.waveform_service import generate_waveform
        from app.services.encryption_service import decrypt_bytes
        from app.config import get_settings

        settings = get_settings()
        async with AsyncSessionLocal() as db:
            loop = await db.get(Loop, uuid.UUID(loop_id))
            if not loop or not loop.file_s3_key:
                return
            s3 = boto3.client(
                "s3",
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_region,
            )
            obj = s3.get_object(Bucket=settings.s3_bucket_name, Key=loop.file_s3_key)
            encrypted = obj["Body"].read()
            wav_bytes = decrypt_bytes(encrypted, loop.aes_key, loop.aes_iv)
            waveform = generate_waveform(wav_bytes)
            loop.waveform_data = waveform
            await db.commit()
    asyncio.run(_run())


@celery_app.task(name="download_tasks.cleanup_expired_downloads")
def cleanup_expired_downloads():
    async def _run():
        from app.database import AsyncSessionLocal
        from app.models.download import Download
        from sqlalchemy import delete
        from datetime import datetime, timezone

        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(Download).where(Download.expires_at < datetime.now(timezone.utc))
            )
            await db.commit()
    asyncio.run(_run())
