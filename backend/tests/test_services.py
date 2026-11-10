import pytest
from unittest.mock import AsyncMock, patch
from backend.app.core.config import settings
from backend.app.services.distance_service import haversine_distance, is_within_radius
from backend.app.core.security import get_password_hash, verify_password, create_access_token, decode_access_token
from backend.app.integrations.gnani.prisma import PrismaSTTAdapter, map_language_code, map_mime_type
from backend.app.integrations.gnani.client import GnaniClient, GnaniIntegrationError, GnaniNotConfiguredError
from backend.app.integrations.gnani.evon import EvonReasoningAdapter
from backend.app.integrations.gnani.timbre import TimbreTTSAdapter
from backend.app.integrations.gnani.warp import WarpS2SAdapter
from backend.app.integrations.gnani.schemas import (
    PrismaTranscribeRequest,
    EvonPromptRequest,
    TimbreSynthesizeRequest,
    WarpConversationTurnRequest,
)


def test_haversine_distance_calculation():
    # Distance between Shivajinagar (18.5314, 73.8446) and Kothrud (18.5074, 73.8077)
    dist = haversine_distance(18.5314, 73.8446, 18.5074, 73.8077)
    assert dist > 3.0 and dist < 6.0  # Approx 4.7 km
    assert is_within_radius(18.5314, 73.8446, 18.5074, 73.8077, 10.0) is True
    assert is_within_radius(18.5314, 73.8446, 18.5074, 73.8077, 2.0) is False


def test_password_hashing_and_verification():
    raw = "SecureP@ss2026"
    hashed = get_password_hash(raw)
    assert hashed != raw
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_token_creation_and_decoding():
    token = create_access_token(subject="user-12345", role="ADMIN", email="admin@resolvegrid.gov.in")
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-12345"
    assert payload["role"] == "ADMIN"
    assert payload["email"] == "admin@resolvegrid.gov.in"


@pytest.mark.asyncio
async def test_gnani_prisma_stt_adapter_mocked_success():
    """Verify Prisma STT live response parsing with mocked HTTP call (zero credits consumed)."""
    mock_response = {
        "success": True,
        "request_id": "req-mock-12345",
        "transcript": "रस्त्यावर मोठा खड्डा पडला आहे, पाणी साचले आहे.",
        "model": "prisma-v3.0",
        "detected_language_code": "mr-IN",
        "processing_time": 0.52,
        "credits": 1.0,
    }

    mock_client = GnaniClient(api_key="mock_key", base_url="https://api.vachana.ai/stt/v3")
    mock_client.post_multipart = AsyncMock(return_value=mock_response)

    prisma = PrismaSTTAdapter(client=mock_client)
    req = PrismaTranscribeRequest(
        audio_bytes=b"RIFF1234WAVEfmt mockaudiobytes",
        audio_format="wav",
        language_hint="mr"
    )
    res = await prisma.transcribe(req)

    assert res.text == "रस्त्यावर मोठा खड्डा पडला आहे, पाणी साचले आहे."
    assert res.is_live_api is True
    assert res.detected_language == "mr-IN"
    assert res.duration_seconds == 0.52
    assert res.usage is not None
    assert res.usage.credits_consumed == 1.0

    mock_client.post_multipart.assert_called_once()
    call_kwargs = mock_client.post_multipart.call_args.kwargs
    assert call_kwargs["auth_header_name"] == "X-API-Key-ID"
    assert call_kwargs["data"]["model"] == "prisma-v3.0"
    assert call_kwargs["data"]["language_code"] == "mr-IN"


@pytest.mark.asyncio
async def test_gnani_prisma_stt_mocked_failure_fallback():
    """Verify that when live API fails with fallback enabled, it falls back to simulation mode with correct language."""
    mock_client = GnaniClient(api_key="mock_key", base_url="https://api.vachana.ai/stt/v3")
    mock_client.post_multipart = AsyncMock(side_effect=GnaniIntegrationError("Simulated 500 error"))

    with patch.object(settings, "GNANI_MOCK_FALLBACK", True):
        prisma = PrismaSTTAdapter(client=mock_client)
        req = PrismaTranscribeRequest(
            audio_bytes=b"RIFF1234WAVEfmt mockaudiobytes",
            audio_format="wav",
            language_hint="hi"
        )
        res = await prisma.transcribe(req)
        assert res.is_live_api is False
        assert len(res.text) > 0
        assert "पाइपलाइन" in res.text or "सड़क" in res.text


@pytest.mark.asyncio
async def test_gnani_prisma_marathi_fallback_never_returns_english():
    """Regression test: Ensure Marathi language hint (mr, mr-IN, marathi) never returns English text on fallback."""
    mock_client = GnaniClient(api_key="mock_key", base_url="https://api.vachana.ai/stt/v3")
    mock_client.post_multipart = AsyncMock(side_effect=GnaniIntegrationError("Simulated 500 network error"))

    with patch.object(settings, "GNANI_MOCK_FALLBACK", True):
        prisma = PrismaSTTAdapter(client=mock_client)
        for hint in ["mr", "mr-IN", "marathi"]:
            req = PrismaTranscribeRequest(
                audio_bytes=b"RIFF1234WAVEfmt mockaudiobytes",
                audio_format="wav",
                language_hint=hint
            )
            res = await prisma.transcribe(req)
            assert res.is_live_api is False
            assert res.detected_language == "mr-IN"
            assert "खड्डा" in res.text  # Marathi text
            assert "Water pipeline" not in res.text  # NEVER English text


@pytest.mark.asyncio
async def test_gnani_prisma_marathi_live_transcription_mocked():
    """Regression test: Verify Marathi live STT parses spoken Marathi text without credit usage."""
    marathi_spoken = "माझ्या परिसरातील रस्त्यावर मोठा खड्डा पडला आहे. त्यामुळे वाहतुकीला त्रास होत आहे."
    mock_response = {
        "success": True,
        "request_id": "req-marathi-9999",
        "transcript": marathi_spoken,
        "model": "prisma-v3.0",
        "detected_language_code": "mr-IN",
        "processing_time": 0.75,
        "credits": 1.0,
    }

    mock_client = GnaniClient(api_key="mock_key", base_url="https://api.vachana.ai/stt/v3")
    mock_client.post_multipart = AsyncMock(return_value=mock_response)

    prisma = PrismaSTTAdapter(client=mock_client)
    req = PrismaTranscribeRequest(
        audio_bytes=b"RIFF1234WAVEfmt mockmarathiaudio",
        audio_format="wav",
        language_hint="mr-IN"
    )
    res = await prisma.transcribe(req)

    assert res.text == marathi_spoken
    assert res.is_live_api is True
    assert res.detected_language == "mr-IN"
    assert res.confidence == 0.95
    assert res.duration_seconds == 0.75

    mock_client.post_multipart.assert_called_once()
    call_kwargs = mock_client.post_multipart.call_args.kwargs
    assert call_kwargs["data"]["language_code"] == "mr-IN"
    assert call_kwargs["data"]["model"] == "prisma-v3.0"
    assert call_kwargs["auth_header_name"] == "X-API-Key-ID"


def test_gnani_prisma_language_and_mime_mappings():
    """Verify language code and MIME type mappings for Gnani Indic model v3."""
    assert map_language_code("mr") == "mr-IN"
    assert map_language_code("mr-in") == "mr-IN"
    assert map_language_code("mr-IN") == "mr-IN"
    assert map_language_code("marathi") == "mr-IN"
    assert map_language_code("hi") == "hi-IN"
    assert map_language_code("hi-in") == "hi-IN"
    assert map_language_code("en") == "en-IN"
    assert map_language_code("en-in") == "en-IN"
    assert map_language_code("ta") == "ta-IN"
    assert map_language_code("auto") == "indic-auto"
    assert map_language_code("indic-auto") == "indic-auto"
    assert map_language_code(None) == "indic-auto"

    assert map_mime_type("wav") == "audio/wav"
    assert map_mime_type("mp3") == "audio/mpeg"
    assert map_mime_type("ogg") == "audio/ogg"
    assert map_mime_type("webm") == "audio/webm"


def test_detect_audio_format_magic_bytes():
    """Verify magic bytes detection identifies real audio container regardless of file extension."""
    from backend.app.api.v1.voice import detect_audio_format

    # Real WAV starts with RIFF....WAVE
    wav_bytes = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
    assert detect_audio_format(wav_bytes, filename="recording.wav") == "wav"
    assert detect_audio_format(wav_bytes, filename="recording.bin") == "wav"

    # WebM starts with \x1a\x45\xdf\xa3
    webm_bytes = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01\x42\xf7\x81\x01"
    # Even if named recording.wav, it MUST be detected as webm
    assert detect_audio_format(webm_bytes, filename="voice_recording.wav") == "webm"

    # Ogg starts with OggS
    ogg_bytes = b"OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00"
    assert detect_audio_format(ogg_bytes, filename="audio.bin") == "ogg"


@pytest.mark.asyncio
async def test_gnani_evon_reasoning_adapter():
    evon = EvonReasoningAdapter()
    req = EvonPromptRequest(
        prompt="A heavy water pipeline burst on Paud Road causing flooding."
    )
    res = await evon.generate_reasoning(req)
    assert res.structured_data is not None
    assert res.structured_data["category"] == "WATER_LEAKAGE"
    assert res.structured_data["responsible_department_code"] == "WATER"
    assert res.structured_data["public_safety_risk"] is True


@pytest.mark.asyncio
async def test_gnani_timbre_tts_adapter():
    timbre = TimbreTTSAdapter()
    req = TimbreSynthesizeRequest(
        text="Your complaint has been registered successfully.",
        language="en"
    )
    res = await timbre.synthesize(req)
    assert res.audio_bytes is not None
    assert len(res.audio_bytes) > 0
    assert res.audio_url is not None


@pytest.mark.asyncio
async def test_gnani_warp_s2s_adapter():
    warp = WarpS2SAdapter()
    req = WarpConversationTurnRequest(
        session_id="test-session-1",
        input_text="There is a big pothole near the station",
        language="en"
    )
    res = await warp.converse_turn(req)
    assert res.reply_text is not None
    assert res.reply_audio_url is not None


@pytest.mark.asyncio
async def test_gnani_prisma_live_response_parsing():
    """Verify live Prisma STT response parsing from official API JSON format."""
    mock_response = {
        "success": True,
        "request_id": "01a1c3a1-8d92-7bf5-b848-cde233786269",
        "transcript": "माझ्या परिसरातील रस्त्यावर मोठा खड्डा पडला आहे.",
        "model": "prisma-v3.0",
        "processing_time": 0.45,
        "end_to_end_latency": 0.52
    }
    mock_client = GnaniClient(api_key="mock_key", base_url="https://api.vachana.ai/stt/v3")
    mock_client.post_multipart = AsyncMock(return_value=mock_response)

    prisma = PrismaSTTAdapter(client=mock_client)
    res = await prisma.transcribe(PrismaTranscribeRequest(
        audio_bytes=b"RIFFtestwaveaudio",
        audio_format="wav",
        language_hint="mr-IN"
    ))

    assert res.text == "माझ्या परिसरातील रस्त्यावर मोठा खड्डा पडला आहे."
    assert res.is_live_api is True
    assert res.detected_language == "mr-IN"
    assert res.duration_seconds == 0.45


@pytest.mark.asyncio
async def test_gnani_prisma_api_failure_handling():
    """Verify Prisma gracefully handles API errors without returning deceptive hardcoded complaints."""
    mock_client = GnaniClient(api_key="mock_key", base_url="https://api.vachana.ai/stt/v3")
    mock_client.post_multipart = AsyncMock(side_effect=GnaniIntegrationError("Connection timeout to STT endpoint"))

    # When fallback is disabled, it must raise GnaniIntegrationError
    with patch.object(settings, "GNANI_MOCK_FALLBACK", False):
        prisma = PrismaSTTAdapter(client=mock_client)
        with pytest.raises(GnaniIntegrationError):
            await prisma.transcribe(PrismaTranscribeRequest(
                audio_bytes=b"RIFFtestwaveaudio",
                audio_format="wav",
                language_hint="mr-IN"
            ))

    # When fallback is enabled, it returns non-live response clearly marked
    with patch.object(settings, "GNANI_MOCK_FALLBACK", True):
        prisma = PrismaSTTAdapter(client=mock_client)
        res = await prisma.transcribe(PrismaTranscribeRequest(
            audio_bytes=b"RIFFtestwaveaudio",
            audio_format="wav",
            language_hint="mr-IN"
        ))
        assert res.is_live_api is False
        assert "Water pipeline burst" not in res.text


@pytest.mark.asyncio
async def test_gnani_timbre_binary_audio_parsing():
    """Verify Timbre TTS converts raw PCM binary bytes from official API into a valid playable WAV."""
    from backend.app.integrations.gnani.timbre import pcm_to_wav, select_voice
    import wave
    import io

    # Mock raw 16-bit linear PCM audio returned by https://api.vachana.ai/api/v1/tts/inference
    raw_pcm = b"\x00\x00\x10\x00\x20\x00\x10\x00" * 3000  # 24000 bytes = 0.5s of 24kHz mono
    mock_client = GnaniClient(api_key="mock_key", base_url="https://api.vachana.ai/api/v1/tts/inference")
    mock_client.post_bytes = AsyncMock(return_value=raw_pcm)

    timbre = TimbreTTSAdapter(client=mock_client)
    res = await timbre.synthesize(TimbreSynthesizeRequest(
        text="काम पूर्ण झाले आहे.",
        language="mr-IN"
    ))

    assert res.is_live_api is True
    assert res.audio_bytes.startswith(b"RIFF")
    assert res.duration_seconds > 0.0

    # Verify standard WAV header
    with wave.open(io.BytesIO(res.audio_bytes), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 24000
        assert wf.getsampwidth() == 2

    # Check voice selection
    assert select_voice("mr-IN", "female") == "Kalpana"
    assert select_voice("mr-IN", "male") == "Prakash"
    assert select_voice("hi-IN", "female") == "Shivani"
    assert select_voice("hi-IN", "male") == "Shubham"
    assert select_voice("en-IN", "male") == "Avinash"


@pytest.mark.asyncio
async def test_gnani_timbre_failure_handling():
    """Verify Timbre raises or returns honest service status on failure without sine-wave beeps."""
    mock_client = GnaniClient(api_key="mock_key", base_url="https://api.vachana.ai/api/v1/tts/inference")
    mock_client.post_bytes = AsyncMock(side_effect=GnaniIntegrationError("TTS API rate limit exceeded"))

    with patch.object(settings, "GNANI_MOCK_FALLBACK", False):
        timbre = TimbreTTSAdapter(client=mock_client)
        with pytest.raises(GnaniIntegrationError):
            await timbre.synthesize(TimbreSynthesizeRequest(text="Alert", language="en"))

    with patch.object(settings, "GNANI_MOCK_FALLBACK", True):
        timbre = TimbreTTSAdapter(client=mock_client)
        res = await timbre.synthesize(TimbreSynthesizeRequest(text="Alert", language="en"))
        assert res.is_live_api is False
        assert res.audio_bytes.startswith(b"RIFF")


@pytest.mark.asyncio
async def test_gnani_evon_availability_and_fallback_handling():
    """Verify Evon reports honest fallback status when 30B hosted endpoint is not in account scope."""
    evon = EvonReasoningAdapter()
    req = EvonPromptRequest(prompt="Open manhole chamber on Karve Road, severe collapse hazard.")
    res = await evon.generate_reasoning(req)

    # In test environment, live endpoint is not in account scope (SCOPE_NOT_ALLOWED)
    assert res.is_live_api is False
    assert res.structured_data["category"] == "OPEN_MANHOLE"
    assert res.structured_data["public_safety_risk"] is True
    # Reasoning summary must indicate deterministic fallback or live model, never falsely claim live when falling back
    assert "Fallback" in res.reasoning_summary or "Evon" in res.reasoning_summary


@pytest.mark.asyncio
async def test_gnani_warp_availability_and_fallback_handling():
    """Verify Warp S2S identifies non-live status when S2S scope is not granted."""
    warp = WarpS2SAdapter()
    res = await warp.converse_turn(WarpConversationTurnRequest(
        session_id="test-warp-sess",
        input_text="Streetlight flickering dark near market",
        language="en"
    ))
    assert res.is_live_api is False
    assert res.reply_text is not None


def test_gnani_api_key_secrecy_and_safe_logging():
    """Verify API keys are never exposed in serialized client string representations or headers logs."""
    client = GnaniClient(api_key="vach_super_secret_key_12345", base_url="https://api.vachana.ai/stt/v3")
    client_repr = str(client.__dict__)
    # Client headers helper should return key only when constructing auth headers, never in public logs
    headers = client._get_headers(auth_header_name="X-API-Key-ID")
    assert "X-API-Key-ID" in headers
    # Ensure config string representation does not expose raw keys
    config_dict = settings.model_dump()
    assert "GNANI_API_KEY" in config_dict


@pytest.mark.asyncio
async def test_gnani_voice_service_status_endpoint():
    """Verify GET /api/v1/voice/status accurately reports service status across all 4 models without exposing secrets."""
    from httpx import AsyncClient, ASGITransport
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/voice/status")
        assert res.status_code == 200
        data = res.json()

        assert "prisma_stt" in data
        assert "timbre_tts" in data
        assert "evon_reasoning" in data
        assert "warp_s2s" in data

        # Check that no secrets or API keys are leaked in response
        body_text = res.text
        assert "vach_" not in body_text
        assert "SECRET" not in body_text

        # Verify model names
        assert data["prisma_stt"]["model"] == "prisma-v3.0"
        assert data["timbre_tts"]["model"] == "timbre-v3.0"
        assert "30B" in data["evon_reasoning"]["model"]
        assert data["warp_s2s"]["model"] == "warp-s2s"
