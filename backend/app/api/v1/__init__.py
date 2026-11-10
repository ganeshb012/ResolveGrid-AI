from fastapi import APIRouter
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.incidents import router as incidents_router
from backend.app.api.v1.voice import router as voice_router
from backend.app.api.v1.workers import router as workers_router
from backend.app.api.v1.assignments import router as assignments_router
from backend.app.api.v1.agents import router as agents_router
from backend.app.api.v1.approvals import router as approvals_router
from backend.app.api.v1.analytics import router as analytics_router
from backend.app.api.v1.users import router as users_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_v1_router.include_router(users_router, prefix="/users", tags=["User Management"])
api_v1_router.include_router(incidents_router, prefix="/incidents", tags=["Incidents"])
api_v1_router.include_router(voice_router, prefix="/voice", tags=["Voice (Gnani AI)"])
api_v1_router.include_router(workers_router, prefix="/workers", tags=["Workers"])
api_v1_router.include_router(assignments_router, prefix="/assignments", tags=["Assignments"])
api_v1_router.include_router(agents_router, prefix="/agents", tags=["Agents (LangGraph)"])
api_v1_router.include_router(approvals_router, prefix="/approvals", tags=["Human Approvals"])
api_v1_router.include_router(analytics_router, prefix="/analytics", tags=["Analytics"])
