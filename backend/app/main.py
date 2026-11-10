import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import settings
from backend.app.api.v1 import api_v1_router
from backend.app.websockets.manager import ws_manager
from backend.app.tasks.manager import task_manager
from backend.app.seeds.seed_data import seed_database
from backend.app.integrations.gnani.client import GnaniClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("resolvegrid.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup:
    logger.info("ResolveGrid AI Backend starting up...")

    # 1. Initialize SQLite schema & seed demo data
    try:
        seed_database()
        logger.info("Database schema validated and seed data loaded.")
    except Exception as e:
        logger.error("Failed to seed database: %s", str(e), exc_info=True)

    # 2. Start unified background task manager (Celery or Async fallback runner)
    await task_manager.start()

    logger.info("ResolveGrid AI platform operational.")
    yield

    # Shutdown:
    logger.info("ResolveGrid AI shutting down...")
    await task_manager.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="ResolveGrid AI — Autonomous Multi-Agent Public Infrastructure Incident Resolution Platform",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded files (evidence photos & generated voice audio)
uploads_path = Path(settings.UPLOAD_DIR).resolve()
uploads_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")

# Include v1 REST API
app.include_router(api_v1_router, prefix=settings.API_V1_STR)


# Real-time WebSocket endpoint
@app.websocket("/ws")
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str = None):
    await ws_manager.connect(websocket, user_id)
    try:
        while True:
            # Keep socket open and receive heartbeat or client messages
            data = await websocket.receive_text()
            # Echo or process if needed
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.warning("WebSocket error: %s", str(e))
        ws_manager.disconnect(websocket, user_id)


# Platform Health & Status Check
@app.get("/health", tags=["System"])
async def health_check():
    from backend.app.integrations.gnani.prisma import PrismaSTTAdapter
    from backend.app.integrations.gnani.evon import EvonReasoningAdapter
    from backend.app.integrations.gnani.timbre import TimbreTTSAdapter
    from backend.app.integrations.gnani.warp import WarpS2SAdapter

    prisma = PrismaSTTAdapter()
    evon = EvonReasoningAdapter()
    timbre = TimbreTTSAdapter()
    warp = WarpS2SAdapter()

    return {
        "status": "healthy",
        "platform": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database": {
            "type": "SQLite",
            "file": settings.DATABASE_URL
        },
        "background_tasks": {
            "mode": task_manager.mode,
            "redis_detected": task_manager.redis_available,
            "celery_broker": settings.REDIS_URL if task_manager.redis_available else None
        },
        "gnani_models": {
            "prisma_stt": {
                "configured": prisma.is_configured,
                "status": "Awaiting Credentials" if not prisma.is_configured else "Active",
                "mode": "Live API" if prisma.is_configured else ("Simulation Fallback" if settings.GNANI_MOCK_FALLBACK else "Disabled")
            },
            "evon_reasoning": {
                "configured": evon.is_configured,
                "status": "Awaiting Credentials" if not evon.is_configured else "Active",
                "mode": "Live API" if evon.is_configured else ("Simulation Fallback" if settings.GNANI_MOCK_FALLBACK else "Disabled")
            },
            "timbre_tts": {
                "configured": timbre.is_configured,
                "status": "Awaiting Credentials" if not timbre.is_configured else "Active",
                "mode": "Live API" if timbre.is_configured else ("Simulation Fallback" if settings.GNANI_MOCK_FALLBACK else "Disabled")
            },
            "warp_s2s": {
                "configured": warp.is_configured,
                "status": "Awaiting Credentials" if not warp.is_configured else "Active",
                "mode": "Live API" if warp.is_configured else ("Simulation Fallback" if settings.GNANI_MOCK_FALLBACK else "Disabled")
            }
        }
    }
