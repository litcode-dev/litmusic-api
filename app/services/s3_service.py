import boto3
from app.config import get_settings

settings = get_settings()


def _get_client():
    return boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )


async def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload bytes to S3. Returns the S3 key."""
    client = _get_client()
    client.put_object(
        Bucket=settings.s3_bucket_name,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return key


async def generate_presigned_url(key: str, expiry_seconds: int = 900) -> str:
    """Generate a pre-signed GET URL valid for expiry_seconds (default 15 min)."""
    client = _get_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket_name, "Key": key},
        ExpiresIn=expiry_seconds,
    )


async def delete_object(key: str) -> None:
    client = _get_client()
    client.delete_object(Bucket=settings.s3_bucket_name, Key=key)


def s3_key_for_encrypted_loop(loop_id: str) -> str:
    return f"loops/encrypted/{loop_id}.wav.enc"


def s3_key_for_loop_preview(loop_id: str) -> str:
    return f"previews/{loop_id}_preview.mp3"


def s3_key_for_encrypted_stem(stem_id: str) -> str:
    return f"stems/encrypted/{stem_id}.wav.enc"


def s3_key_for_stem_preview(stem_id: str) -> str:
    return f"stems/previews/{stem_id}_preview.mp3"
