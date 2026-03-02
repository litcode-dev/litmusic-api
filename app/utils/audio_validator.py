import io
import soundfile as sf
from fastapi import UploadFile
from app.exceptions import AppError

MAX_FILE_SIZE_BYTES = 30 * 1024 * 1024  # 30 MB
REQUIRED_SAMPLE_RATE = 44100


async def validate_wav_upload(file: UploadFile) -> bytes:
    """Read, size-check, and format-validate an uploaded WAV. Returns raw bytes."""
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise AppError("File exceeds 30 MB limit", status_code=413)

    try:
        audio, sample_rate = sf.read(io.BytesIO(content))
    except Exception:
        raise AppError("Invalid audio file — must be a valid WAV", status_code=422)

    if sample_rate != REQUIRED_SAMPLE_RATE:
        raise AppError(
            f"Sample rate must be 44100 Hz, got {sample_rate} Hz", status_code=422
        )

    return content
