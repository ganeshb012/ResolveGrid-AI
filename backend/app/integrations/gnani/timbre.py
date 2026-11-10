import io
import logging
import wave
import uuid
from pathlib import Path
from typing import Optional
from backend.app.core.config import settings
from backend.app.integrations.gnani.client import GnaniClient, GnaniNotConfiguredError, GnaniIntegrationError
from backend.app.integrations.gnani.schemas import (
    TimbreSynthesizeRequest,
    TimbreSynthesizeResponse,
)

logger = logging.getLogger("resolvegrid.gnani.timbre")


def pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 24000, channels: int = 1) -> bytes:
    """Wrap raw 16-bit linear PCM audio in a standard playable RIFF/WAVE container."""
    if pcm_bytes.startswith(b"RIFF"):
        return pcm_bytes
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def select_voice(language: str, gender: Optional[str] = None) -> str:
    """
    Select appropriate Gnani Timbre voice.
    Supported voices: Avinash, Shivani, Lakshmi, Kalpana, Shubham, Prakash, Devansh, Yashraj, Chetana, Vasudha, Harshad, Riyaa, Tarika.
    """
    lang = (language or "en").lower().strip()
    g = (gender or "neutral").lower()

    if "mr" in lang:  # Marathi
        return "Prakash" if g == "male" else "Kalpana"
    elif "hi" in lang:  # Hindi
        return "Shubham" if g == "male" else "Shivani"
    else:  # English / Default
        return "Avinash" if g == "male" else "Kalpana"


def map_language_for_tts(lang: str) -> str:
    lang_lower = (lang or "en").lower().strip()
    if "mr" in lang_lower:
        return "mr-IN"
    if "hi" in lang_lower:
        return "hi-IN"
    return "en-IN"


def generate_silent_wav(duration_sec: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Generate quiet audio buffer without synthetic sine-wave beeps for mock/offline testing."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        num_frames = int(sample_rate * duration_sec)
        wf.writeframes(b"\x00\x00" * num_frames)
    return buf.getvalue()


class TimbreTTSAdapter:
    """
    Adapter for Gnani Timbre (Vachana TTS v3) — Text-to-Speech Model.
    Official endpoint: POST https://api.vachana.ai/api/v1/tts/inference
    Header: X-API-Key-ID
    Generates high-fidelity synthesized audio for worker dispatch and citizen voice updates.
    """

    def __init__(self, client: Optional[GnaniClient] = None):
        self.client = client or GnaniClient(base_url=settings.GNANI_TIMBRE_URL)
        self.audio_dir = settings.UPLOAD_DIR / "audio"
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    @property
    def is_configured(self) -> bool:
        return self.client.is_configured

    async def synthesize(self, request: TimbreSynthesizeRequest) -> TimbreSynthesizeResponse:
        audio_filename = f"timbre_{uuid.uuid4().hex[:12]}.wav"
        output_file = self.audio_dir / audio_filename

        lang_code = map_language_for_tts(request.language)
        voice_name = select_voice(lang_code, request.voice_gender)

        if self.is_configured:
            try:
                payload = {
                    "model": "timbre-v3.0",
                    "text": request.text,
                    "voice": voice_name,
                    "language": lang_code,
                }
                logger.info(
                    "Submitting live TTS to Gnani Timbre: voice=%s, lang=%s, chars=%d",
                    voice_name, lang_code, len(request.text)
                )

                # Live binary audio stream (raw PCM or WAV)
                audio_raw = await self.client.post_bytes(
                    endpoint="",
                    payload=payload,
                    auth_header_name="X-API-Key-ID"
                )

                wav_bytes = pcm_to_wav(audio_raw, sample_rate=24000)
                with open(output_file, "wb") as f:
                    f.write(wav_bytes)

                duration = len(audio_raw) / (2 * 24000) if not audio_raw.startswith(b"RIFF") else max(1.0, len(request.text.split()) * 0.4)

                logger.info(
                    "Gnani Timbre (Live) TTS completed: size=%d bytes, duration=%.2fs -> %s",
                    len(wav_bytes), duration, audio_filename
                )

                return TimbreSynthesizeResponse(
                    audio_bytes=wav_bytes,
                    audio_url=f"/uploads/audio/{audio_filename}",
                    duration_seconds=duration,
                    language=lang_code,
                    audio_format="wav",
                    is_live_api=True
                )
            except Exception as e:
                logger.error("Timbre live synthesis failed: %s", str(e))
                if not settings.GNANI_MOCK_FALLBACK:
                    raise GnaniIntegrationError(f"Timbre live synthesis failed: {e}") from e

        if not settings.GNANI_MOCK_FALLBACK:
            raise GnaniNotConfiguredError(
                "Gnani Timbre (TTS) is awaiting API credentials in environment variables (GNANI_API_KEY/GNANI_TIMBRE_URL)."
            )

        # Simulation fallback generates compliant silent WAV (no sine-wave tones)
        duration = max(1.5, len(request.text.split()) * 0.35)
        raw_wav = generate_silent_wav(duration_sec=min(duration, 3.0), sample_rate=16000)

        with open(output_file, "wb") as f:
            f.write(raw_wav)

        logger.info(
            "Gnani Timbre [Simulation Mode]: Generated placeholder audio (%s, %d bytes) -> %s",
            lang_code, len(raw_wav), audio_filename
        )

        return TimbreSynthesizeResponse(
            audio_bytes=raw_wav,
            audio_url=f"/uploads/audio/{audio_filename}",
            duration_seconds=duration,
            language=lang_code,
            audio_format="wav",
            is_live_api=False
        )
