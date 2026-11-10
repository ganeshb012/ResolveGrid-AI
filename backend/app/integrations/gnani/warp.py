import logging
import uuid
from typing import Optional
from backend.app.core.config import settings
from backend.app.integrations.gnani.client import GnaniClient, GnaniNotConfiguredError
from backend.app.integrations.gnani.schemas import (
    WarpConversationTurnRequest,
    WarpConversationTurnResponse,
)
from backend.app.integrations.gnani.timbre import generate_silent_wav

logger = logging.getLogger("resolvegrid.gnani.warp")


class WarpS2SAdapter:
    """
    Adapter for Gnani Warp — Speech-to-Speech Model.
    Supports real-time conversational voice interaction for hands-free citizen reporting
    and worker updates.
    """

    def __init__(self, client: Optional[GnaniClient] = None):
        self.client = client or GnaniClient(base_url=settings.GNANI_WARP_URL)
        self.audio_dir = settings.UPLOAD_DIR / "audio"
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    @property
    def is_configured(self) -> bool:
        return self.client.is_configured

    async def converse_turn(self, request: WarpConversationTurnRequest) -> WarpConversationTurnResponse:
        session_id = request.session_id or str(uuid.uuid4())

        if self.is_configured:
            try:
                payload = {
                    "session_id": session_id,
                    "language": request.language,
                    "input_text": request.input_text,
                    "context_data": request.context_data or {},
                }
                result = await self.client.post_json("converse", payload)
                return WarpConversationTurnResponse(
                    session_id=session_id,
                    reply_text=result.get("reply_text", ""),
                    reply_audio_url=result.get("reply_audio_url"),
                    detected_intent=result.get("intent"),
                    extracted_fields=result.get("extracted_fields"),
                    is_live_api=True
                )
            except Exception as e:
                logger.error("Warp live S2S converse failed: %s", str(e))
                if not settings.GNANI_MOCK_FALLBACK:
                    raise

        if not settings.GNANI_MOCK_FALLBACK:
            raise GnaniNotConfiguredError(
                "Gnani Warp (Speech-to-Speech) is awaiting API credentials in environment variables (GNANI_API_KEY/GNANI_WARP_URL)."
            )

        # Conversational dialog state simulation
        prompt_in = (request.input_text or "").lower()
        if any(w in prompt_in for w in ["hello", "hi", "namaste", "नमस्कार"]):
            reply = "Hello! Welcome to ResolveGrid AI citizen assistance. What infrastructure issue would you like to report?"
            intent = "GREETING"
        elif any(w in prompt_in for w in ["pothole", "road", "खड्डा"]):
            reply = "I understand there is road damage or a pothole. Could you please specify the street or landmark near Pune?"
            intent = "REPORT_ROAD"
        elif any(w in prompt_in for w in ["water", "leak", "पाणी"]):
            reply = "I registered a water leakage report. Is water continuously overflowing right now?"
            intent = "REPORT_WATER"
        else:
            reply = "Thank you. Your incident details have been noted. The location and severity will be assessed immediately."
            intent = "GENERAL_REPORT"

        # Synthesize real spoken audio reply using Gnani Timbre TTS engine
        audio_url = None
        raw_wav = b""
        is_live_tts = False
        try:
            from backend.app.integrations.gnani.timbre import TimbreTTSAdapter
            from backend.app.integrations.gnani.schemas import TimbreSynthesizeRequest
            tts = TimbreTTSAdapter()
            synth = await tts.synthesize(TimbreSynthesizeRequest(
                text=reply,
                language=request.language or "en",
                voice_gender="neutral"
            ))
            audio_url = synth.audio_url
            raw_wav = synth.audio_bytes
            is_live_tts = synth.is_live_api
        except Exception as e:
            logger.warning("Warp TTS voice synthesis fallback: %s", e)
            audio_filename = f"warp_{uuid.uuid4().hex[:12]}.wav"
            output_file = self.audio_dir / audio_filename
            raw_wav = generate_silent_wav(duration_sec=2.0)
            with open(output_file, "wb") as f:
                f.write(raw_wav)
            audio_url = f"/uploads/audio/{audio_filename}"

        logger.info("Gnani Warp Conversational Turn: Session %s -> Reply: '%s' (Audio: %s)", session_id, reply[:40], audio_url)

        return WarpConversationTurnResponse(
            session_id=session_id,
            reply_text=reply,
            reply_audio_bytes=raw_wav,
            reply_audio_url=audio_url,
            detected_intent=intent,
            extracted_fields={"language": request.language},
            is_live_api=is_live_tts
        )
