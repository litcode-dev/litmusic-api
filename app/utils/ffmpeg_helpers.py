import subprocess
import os
import tempfile
from pathlib import Path


def generate_preview_mp3(wav_bytes: bytes, duration_seconds: int = 15) -> bytes:
    """
    Cut the first duration_seconds of a WAV and encode to MP3 using ffmpeg.
    Returns MP3 bytes.
    """
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_in:
        tmp_in.write(wav_bytes)
        tmp_in_path = tmp_in.name

    tmp_out_path = str(Path(tmp_in_path).with_suffix("")) + "_preview.mp3"
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", tmp_in_path,
                "-t", str(duration_seconds),
                "-q:a", "2",
                "-vn",
                tmp_out_path,
            ],
            check=True,
            capture_output=True,
        )
        with open(tmp_out_path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(tmp_in_path):
            os.unlink(tmp_in_path)
        if os.path.exists(tmp_out_path):
            os.unlink(tmp_out_path)
