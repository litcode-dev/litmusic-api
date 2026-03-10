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


def trim_wav_to_duration(wav_bytes: bytes, max_seconds: int = 60) -> bytes:
    """
    If the WAV is longer than max_seconds, trim it. Returns WAV bytes.
    If shorter or equal, returns the original bytes unchanged.
    """
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_in:
        tmp_in.write(wav_bytes)
        tmp_in_path = tmp_in.name

    tmp_out_path = str(Path(tmp_in_path).with_suffix("")) + "_trimmed.wav"
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", tmp_in_path],
            capture_output=True, text=True,
        )
        duration = float(result.stdout.strip() or 0)
        if duration <= max_seconds:
            return wav_bytes

        subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_in_path, "-t", str(max_seconds), "-c", "copy", tmp_out_path],
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


def convert_mp3_to_wav(mp3_bytes: bytes) -> bytes:
    """Convert MP3 bytes to WAV bytes using ffmpeg. Used for Suno-generated audio."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_in:
        tmp_in.write(mp3_bytes)
        tmp_in_path = tmp_in.name

    tmp_out_path = str(Path(tmp_in_path).with_suffix("")) + "_converted.wav"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_in_path, "-ar", "44100", "-ac", "2", tmp_out_path],
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
