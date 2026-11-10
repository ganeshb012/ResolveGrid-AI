import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app


@pytest.mark.asyncio
async def test_health_check_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "gnani_models" in data
    assert "background_tasks" in data


@pytest.mark.asyncio
async def test_auth_login_admin():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/v1/auth/login", json={
            "email": "admin@resolvegrid.gov.in",
            "password": "Admin@12345"
        })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "ADMIN"


@pytest.mark.asyncio
async def test_list_incidents():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/incidents")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_create_incident_and_trigger_workflow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/v1/incidents", json={
            "title": "Broken streetlight outside hospital gate",
            "description": "The lamp post is dark and sparking, creating a safety hazard for ambulances and pedestrians at night.",
            "category": "STREETLIGHT",
            "priority": "HIGH",
            "latitude": 18.5204,
            "longitude": 73.8567,
            "address": "Opposite Sassoon General Hospital, Pune Station Road, Pune 411001",
            "source": "TEXT"
        })
    assert response.status_code == 201
    data = response.json()
    assert data["incident_number"].startswith("INC-")
    assert data["status"] == "REPORTED"


@pytest.mark.asyncio
async def test_analytics_overview():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        unauth_resp = await ac.get("/api/v1/analytics/overview")
        assert unauth_resp.status_code == 401

        admin_login = await ac.post("/api/v1/auth/login", json={
            "email": "admin@resolvegrid.gov.in",
            "password": "Admin@12345"
        })
        assert admin_login.status_code == 200
        admin_token = admin_login.json()["access_token"]

        response = await ac.get(
            "/api/v1/analytics/overview",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
    assert response.status_code == 200
    data = response.json()
    assert "incidents" in data
    assert "workers" in data
    assert "departments" in data
    assert data["incidents"]["total"] >= 1


@pytest.mark.asyncio
async def test_voice_transcribe_endpoint_mocked():
    from unittest.mock import AsyncMock, patch
    from backend.app.integrations.gnani.schemas import PrismaTranscribeResponse

    mock_res = PrismaTranscribeResponse(
        text="रस्त्यावर मोठा खड्डा पडला आहे.",
        confidence=0.98,
        detected_language="mr-IN",
        duration_seconds=0.45,
        is_live_api=True
    )

    with patch("backend.app.integrations.gnani.prisma.PrismaSTTAdapter.transcribe", new=AsyncMock(return_value=mock_res)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            files = {"file": ("audio.wav", b"RIFF1234WAVEfmt mockbytes", "audio/wav")}
            data = {"language": "mr"}
            response = await ac.post("/api/v1/voice/transcribe", files=files, data=data)

        assert response.status_code == 200
        res_data = response.json()
        assert res_data["text"] == "रस्त्यावर मोठा खड्डा पडला आहे."
        assert res_data["provider"] == "Gnani Prisma (Live)"
        assert res_data["detected_language"] == "mr-IN"


@pytest.mark.asyncio
async def test_voice_transcribe_endpoint_default_auto_indic():
    """Verify that omitting language defaults to indic-auto and passes correct format to adapter."""
    from unittest.mock import AsyncMock, patch
    from backend.app.integrations.gnani.schemas import PrismaTranscribeResponse

    mock_res = PrismaTranscribeResponse(
        text="माझ्या परिसरातील रस्त्यावर खड्डा आहे.",
        confidence=0.97,
        detected_language="mr-IN",
        duration_seconds=0.6,
        is_live_api=True
    )

    mock_transcribe = AsyncMock(return_value=mock_res)
    with patch("backend.app.integrations.gnani.prisma.PrismaSTTAdapter.transcribe", new=mock_transcribe):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Upload a WebM file masquerading with .wav filename
            webm_bytes = b"\x1a\x45\xdf\xa3" + b"\x00" * 32
            files = {"file": ("voice_recording.wav", webm_bytes, "audio/webm")}
            response = await ac.post("/api/v1/voice/transcribe", files=files)

        assert response.status_code == 200
        res_data = response.json()
        assert res_data["text"] == "माझ्या परिसरातील रस्त्यावर खड्डा आहे."
        assert res_data["detected_language"] == "mr-IN"

        # Verify adapter received correct detected format 'webm' and language 'indic-auto'
        mock_transcribe.assert_called_once()
        req_arg = mock_transcribe.call_args[0][0]
        assert req_arg.audio_format == "webm"
        assert req_arg.language_hint == "indic-auto"
