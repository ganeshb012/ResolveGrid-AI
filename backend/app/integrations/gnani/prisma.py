import logging
import time
from typing import Optional
from backend.app.core.config import settings
from backend.app.integrations.gnani.client import GnaniClient, GnaniNotConfiguredError, GnaniIntegrationError
from backend.app.integrations.gnani.schemas import (
    PrismaTranscribeRequest,
    PrismaTranscribeResponse,
    GnaniUsage,
)

logger = logging.getLogger("resolvegrid.gnani.prisma")


def map_language_code(language_hint: Optional[str]) -> str:
    """Map standard language tags (en, hi, mr) or BCP-47 codes to Gnani Indic language codes."""
    if not language_hint or language_hint.strip().lower() in ["auto", "indic-auto"]:
        return "indic-auto"
    hint_lower = language_hint.lower().strip()
    mapping = {
        "mr": "mr-IN",
        "mr-in": "mr-IN",
        "marathi": "mr-IN",
        "hi": "hi-IN",
        "hi-in": "hi-IN",
        "hindi": "hi-IN",
        "en": "en-IN",
        "en-in": "en-IN",
        "english": "en-IN",
        "ta": "ta-IN",
        "ta-in": "ta-IN",
        "tamil": "ta-IN",
        "te": "te-IN",
        "te-in": "te-IN",
        "telugu": "te-IN",
        "kn": "kn-IN",
        "kn-in": "kn-IN",
        "kannada": "kn-IN",
        "gu": "gu-IN",
        "gu-in": "gu-IN",
        "gujarati": "gu-IN",
        "bn": "bn-IN",
        "bn-in": "bn-IN",
        "bengali": "bn-IN",
    }
    return mapping.get(hint_lower, hint_lower)


def map_mime_type(audio_format: str) -> str:
    """Map audio extension to appropriate standard MIME type for multipart upload."""
    fmt = audio_format.lower().lstrip(".")
    mimes = {
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "ogg": "audio/ogg",
        "webm": "audio/webm",
        "flac": "audio/flac",
        "m4a": "audio/mp4",
        "aac": "audio/aac",
    }
    return mimes.get(fmt, "audio/wav")


class PrismaSTTAdapter:
    """
    Adapter for Gnani Prisma (Vachana STT v3) — Speech-to-Text Model.
    Endpoint: POST https://api.vachana.ai/stt/v3
    Header: X-API-Key-ID
    Supports Marathi, Hindi, English, and other Indic languages with auto-detection.
    """

    def __init__(self, client: Optional[GnaniClient] = None):
        self.client = client or GnaniClient(base_url=settings.GNANI_PRISMA_URL)

    @property
    def is_configured(self) -> bool:
        return self.client.is_configured

    @staticmethod
    def _transcode_to_wav(audio_bytes: bytes) -> tuple[bytes, str]:
        """Convert input audio (e.g. browser WebM/Opus) into standard 16kHz mono 16-bit PCM WAV.
        Gnani Prisma STT requires wav, mp3, m4a, ogg, aac, or flac."""
        try:
            import av, io, wave
            in_buf = io.BytesIO(audio_bytes)
            container = av.open(in_buf)
            audio_stream = next((s for s in container.streams if s.type == "audio"), None)
            if not audio_stream:
                return audio_bytes, "wav"

            resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
            out_wav = io.BytesIO()
            with wave.open(out_wav, "wb") as wo:
                wo.setnchannels(1)
                wo.setsampwidth(2)
                wo.setframerate(16000)
                for frame in container.decode(audio_stream):
                    for rf in resampler.resample(frame):
                        wo.writeframes(bytes(rf.planes[0]))
            wav_data = out_wav.getvalue()
            if len(wav_data) > 44:
                return wav_data, "wav"
        except Exception as e:
            logger.warning("Audio transcoding to WAV failed: %s", e)
        return audio_bytes, "wav"

    async def transcribe(self, request: PrismaTranscribeRequest) -> PrismaTranscribeResponse:
        start_time = time.time()

        if self.is_configured:
            try:
                lang_code = map_language_code(request.language_hint)
                fmt = (request.audio_format or "wav").lower().lstrip(".")
                audio_data = request.audio_bytes

                # Transcode unsupported containers (like WebM from browser MediaRecorder) to 16kHz WAV
                if fmt not in ["wav", "mp3", "m4a", "ogg", "aac", "flac"] or audio_data.startswith(b"\x1a\x45\xdf\xa3"):
                    audio_data, fmt = self._transcode_to_wav(audio_data)

                mime_type = map_mime_type(fmt)
                filename = f"audio.{fmt}"

                files = {
                    "audio_file": (filename, audio_data, mime_type)
                }
                form_data = {
                    "model": "prisma-v3.0",
                    "language_code": lang_code,
                }

                logger.info(
                    "Submitting STT to Gnani Prisma v3: lang=%s, format=%s, size=%d bytes",
                    lang_code, fmt, len(audio_data)
                )

                # POST https://api.vachana.ai/stt/v3 with X-API-Key-ID
                result = await self.client.post_multipart(
                    endpoint="",
                    files=files,
                    data=form_data,
                    auth_header_name="X-API-Key-ID"
                )

                elapsed = time.time() - start_time
                transcript_text = (
                    result.get("transcript")
                    or result.get("text")
                    or result.get("data", {}).get("transcript")
                    or ""
                )

                detected_lang = (
                    result.get("detected_language_code")
                    or result.get("detected_language")
                    or request.language_hint
                    or "en"
                )

                duration = float(
                    result.get("processing_time")
                    or result.get("duration")
                    or elapsed
                )

                credits = float(result.get("credits") or 1.0)

                logger.info(
                    "Gnani Prisma (Live) STT completed in %.2fs: detected_lang=%s, length=%d chars",
                    elapsed, detected_lang, len(transcript_text)
                )

                return PrismaTranscribeResponse(
                    text=transcript_text,
                    confidence=float(result.get("confidence", 0.95)),
                    detected_language=detected_lang,
                    duration_seconds=duration,
                    usage=GnaniUsage(
                        audio_seconds=duration,
                        credits_consumed=credits
                    ),
                    is_live_api=True
                )
            except Exception as e:
                logger.error("Prisma live API invocation failed: %s", str(e))
                if not settings.GNANI_MOCK_FALLBACK:
                    raise
                logger.warning("Prisma falling back to local simulation mode after live API error.")

        # When credentials are not yet supplied or fallback is triggered:
        if not settings.GNANI_MOCK_FALLBACK:
            raise GnaniNotConfiguredError(
                "Gnani Prisma (STT) is awaiting API credentials in environment variables (GNANI_API_KEY/GNANI_PRISMA_URL)."
            )

        # High-accuracy multilingual dev transcription simulation
        elapsed = time.time() - start_time
        hint_clean = (request.language_hint or "indic-auto").lower().strip()
        if "en" in hint_clean or "english" in hint_clean:
            lang_key = "en"
            detected_lang = "en-IN"
        elif "hi" in hint_clean or "hindi" in hint_clean:
            lang_key = "hi"
            detected_lang = "hi-IN"
        elif "mr" in hint_clean or "marathi" in hint_clean:
            lang_key = "mr"
            detected_lang = "mr-IN"
        else:
            lang_key = "en"
            detected_lang = "en-IN"

        transcripts = {
            "en": "Electricity is gone in my lane, please resolve this problem quickly.",
            "mr": "माझ्या परिसरातील रस्त्यावर मोठा खड्डा पडला आहे. त्यामुळे वाहतुकीला त्रास होत आहे.",
            "hi": "सड़क पर बड़ा गड्ढा हो गया है, जिससे यातायात में भारी परेशानी हो रही है।",
        }
        text = transcripts[lang_key]

        logger.info("Gnani Prisma [Simulation Mode]: Transcribed audio (%s, lang=%s)", request.audio_format, detected_lang)
        return PrismaTranscribeResponse(
            text=text,
            confidence=0.96,
            detected_language=detected_lang,
            duration_seconds=3.5,
            usage=GnaniUsage(audio_seconds=3.5, credits_consumed=0.0),
            is_live_api=False
        )
