from typing import Optional
from pydantic import BaseModel


class TranscriptionResponse(BaseModel):
    text: str
    confidence: float
    detected_language: str
    provider: str
    latency_ms: int
    is_live: bool = False
    service_status: str = "LIVE"


class SpeakRequest(BaseModel):
    text: str
    language: str = "en"  # en, mr, hi
    voice_gender: Optional[str] = "neutral"


class SpeakResponse(BaseModel):
    audio_url: str
    audio_base64: Optional[str] = None
    language: str
    provider: str
    duration_estimate_sec: float
    is_live: bool = False
    service_status: str = "LIVE"


class ConversationRequest(BaseModel):
    session_id: str
    audio_base64: Optional[str] = None
    text_message: Optional[str] = None
    language: str = "en"


class ConversationResponse(BaseModel):
    session_id: str
    reply_text: str
    reply_audio_url: Optional[str] = None
    detected_intent: Optional[str] = None
    extracted_fields: Optional[dict] = None
    is_live: bool = False
    service_status: str = "SIMULATED"


class ServiceHealth(BaseModel):
    service_name: str
    status: str  # LIVE, SIMULATED, UNAVAILABLE, ERROR
    model: str
    endpoint: Optional[str] = None
    is_live: bool
    details: Optional[str] = None


class GnaniServicesStatusResponse(BaseModel):
    prisma_stt: ServiceHealth
    timbre_tts: ServiceHealth
    evon_reasoning: ServiceHealth
    warp_s2s: ServiceHealth
