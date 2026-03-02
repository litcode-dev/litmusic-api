import io
import numpy as np
import soundfile as sf


def generate_waveform(audio_bytes: bytes, num_points: int = 200) -> list[float]:
    """
    Compute peak-normalised waveform data for frontend visualiser.
    Returns a list of num_points floats in [0.0, 1.0].
    """
    audio, _ = sf.read(io.BytesIO(audio_bytes))
    # Mix to mono if stereo
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    # Split into chunks and take peak amplitude per chunk
    chunk_size = max(1, len(audio) // num_points)
    peaks = []
    for i in range(num_points):
        start = i * chunk_size
        chunk = audio[start : start + chunk_size]
        peaks.append(float(np.abs(chunk).max()) if len(chunk) else 0.0)

    # Normalise to [0, 1]
    max_peak = max(peaks) if peaks else 1.0
    if max_peak == 0:
        return [0.0] * num_points
    return [round(p / max_peak, 4) for p in peaks]
