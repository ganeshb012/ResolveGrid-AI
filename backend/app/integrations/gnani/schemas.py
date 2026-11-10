from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GnaniUsage(BaseModel):
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    audio_seconds: Optional[float] = None
    credits_consumed: Optional[float] = None


# --- Prisma (STT) Schemas ---
class PrismaTranscribeRequest(BaseModel):
    audio_bytes: bytes
    audio_format: str = "wav"  # wav, mp3, ogg, webm
    sample_rate: int = 16000
    language_hint: Optional[str] = "en"  # en, hi, mr
    encoding: Optional[str] = None


class PrismaTranscribeResponse(BaseModel):
    text: str
    confidence: float = 1.0
    detected_language: str = "en"
    duration_seconds: float = 0.0
    usage: Optional[GnaniUsage] = None
    is_live_api: bool = False


# --- Evon (LLM / Reasoning) Schemas ---
class EvonPromptRequest(BaseModel):
    prompt: str
    system_instruction: Optional[str] = None
    temperature: float = 0.2
    max_tokens: int = 1000
    response_format: Optional[str] = "json"


class EvonStructuredIncident(BaseModel):
    title: str
    category: str  # WATER_LEAKAGE, ROAD_POTHOLE, STREETLIGHT, GARBAGE_OVERFLOW, OPEN_MANHOLE, DRAINAGE, OTHER
    detected_location: Optional[str] = None
    landmark: Optional[str] = None
    severity_level: str = "MEDIUM"  # CRITICAL, HIGH, MEDIUM, LOW
    public_safety_risk: bool = False
    urgency_reason: Optional[str] = None
    confidence: float = 0.95
    responsible_department_code: str = "GENERAL"


class EvonReasoningResponse(BaseModel):
    raw_response: str
    structured_data: Optional[Dict[str, Any]] = None
    reasoning_summary: str
    suggested_actions: List[str] = []
    usage: Optional[GnaniUsage] = None
    is_live_api: bool = False


# --- Timbre (TTS) Schemas ---
class TimbreSynthesizeRequest(BaseModel):
    text: str
    language: str = "en"  # en, mr, hi
    voice_gender: str = "neutral"  # male, female, neutral
    audio_format: str = "wav"
    speaking_rate: float = 1.0


class TimbreSynthesizeResponse(BaseModel):
    audio_bytes: bytes
    audio_url: Optional[str] = None
    duration_seconds: float = 0.0
    language: str
    audio_format: str
    is_live_api: bool = False


# --- Warp (Speech-to-Speech) Schemas ---
class WarpConversationTurnRequest(BaseModel):
    session_id: str
    input_audio_bytes: Optional[bytes] = None
    input_text: Optional[str] = None
    language: str = "en"
    context_data: Optional[Dict[str, Any]] = None


class WarpConversationTurnResponse(BaseModel):
    session_id: str
    reply_text: str
    reply_audio_bytes: Optional[bytes] = None
    reply_audio_url: Optional[str] = None
    detected_intent: Optional[str] = None
    extracted_fields: Optional[Dict[str, Any]] = None
    is_live_api: bool = False
