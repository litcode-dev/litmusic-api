import asyncio
from decimal import Decimal
from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def generate_ai_loop_task(self, generation_id: str):
    asyncio.run(_run(generation_id))


async def _run(generation_id: str):
    import uuid
    import io
    import soundfile as sf
    from app.database import AsyncSessionLocal
    from app.models.ai_generation import AIGeneration, AIGenerationStatus, AIProvider
    from app.models.loop import Loop, Genre, TempoFeel
    from app.models.subscription import Subscription
    from app.models.user import User
    from app.services import ai_service, s3_service, encryption_service
    from app.services.loop_service import _slugify
    from app.utils.ffmpeg_helpers import generate_preview_mp3, convert_mp3_to_wav
    from app.tasks.download_tasks import generate_waveform_task

    async with AsyncSessionLocal() as db:
        gen = await db.get(AIGeneration, uuid.UUID(generation_id))
        if not gen:
            return

        gen.status = AIGenerationStatus.processing
        await db.commit()

        try:
            # Call AI provider — Suno returns MP3, self-hosted returns WAV
            audio_bytes = await ai_service.generate_audio(
                gen.provider, gen.prompt, gen.style_prompt
            )

            # Convert Suno MP3 → WAV for the pipeline
            if gen.provider == AIProvider.suno:
                wav_bytes = convert_mp3_to_wav(audio_bytes)
            else:
                wav_bytes = audio_bytes

            # Build Loop using the same components as loop_service.create_loop()
            loop_id = str(uuid.uuid4())
            aes_key, aes_iv = encryption_service.generate_key_and_iv()
            encrypted_wav = encryption_service.encrypt_bytes(wav_bytes, aes_key, aes_iv)
            preview_mp3 = generate_preview_mp3(wav_bytes)

            enc_key = s3_service.s3_key_for_encrypted_loop(loop_id)
            prev_key = s3_service.s3_key_for_loop_preview(loop_id)
            await s3_service.upload_bytes(enc_key, encrypted_wav)
            await s3_service.upload_bytes(prev_key, preview_mp3, "audio/mpeg")

            audio_data, sr = sf.read(io.BytesIO(wav_bytes))
            duration = int(len(audio_data) / sr)

            title = gen.prompt[:100]
            loop = Loop(
                id=uuid.UUID(loop_id),
                title=title,
                slug=_slugify(title, loop_id),
                genre=Genre.afrobeat,
                bpm=120,
                key="C major",
                duration=duration,
                tempo_feel=TempoFeel.mid,
                tags=["ai-generated"],
                price=Decimal("0"),
                is_free=True,
                is_paid=False,
                file_s3_key=enc_key,
                preview_s3_key=prev_key,
                aes_key=aes_key,
                aes_iv=aes_iv,
                created_by=gen.user_id,
            )
            db.add(loop)
            gen.result_loop_id = loop.id
            gen.status = AIGenerationStatus.completed
            await db.commit()

            # Queue waveform generation
            generate_waveform_task.delay(loop_id)

        except Exception as exc:
            gen.status = AIGenerationStatus.failed
            gen.error_message = str(exc)[:500]

            # Refund quota or extra credit on failure
            if gen.is_extra:
                user = await db.get(User, gen.user_id)
                if user:
                    user.ai_extra_credits += 1
            elif gen.subscription_id:
                sub = await db.get(Subscription, gen.subscription_id)
                if sub and sub.ai_quota_used > 0:
                    sub.ai_quota_used -= 1

            await db.commit()
            raise
