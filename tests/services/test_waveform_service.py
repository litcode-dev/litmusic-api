import numpy as np
import soundfile as sf
import io
from app.services.waveform_service import generate_waveform


def _make_wav_bytes(duration_sec: float = 1.0, sr: int = 44100) -> bytes:
    t = np.linspace(0, duration_sec, int(sr * duration_sec))
    samples = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, samples, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def test_waveform_has_correct_length():
    wav = _make_wav_bytes()
    result = generate_waveform(wav, num_points=100)
    assert len(result) == 100


def test_waveform_values_normalised():
    wav = _make_wav_bytes()
    result = generate_waveform(wav)
    assert all(0.0 <= v <= 1.0 for v in result)
    assert max(result) == 1.0


def test_waveform_silent_audio():
    sr = 44100
    silent = np.zeros(sr, dtype=np.float32)
    buf = io.BytesIO()
    sf.write(buf, silent, sr, format="WAV", subtype="PCM_16")
    result = generate_waveform(buf.getvalue())
    assert all(v == 0.0 for v in result)
