from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=5)
    category: Optional[str] = "OTHER"  # May be refined by Incident Intelligence Agent
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    address: str = Field(..., min_length=3)
    landmark: Optional[str] = None
    priority: Optional[str] = "MEDIUM"
    source: str = "TEXT"  # TEXT, VOICE, MOBILE_PORTAL
    original_audio_path: Optional[str] = None
    language: Optional[str] = "en"


class IncidentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    department_id: Optional[str] = None
    landmark: Optional[str] = None
    requires_human_approval: Optional[bool] = None


class IncidentStatusHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    old_status: Optional[str] = None
    new_status: str
    change_reason: Optional[str] = None
    trigger_type: str
    timestamp: datetime


class IncidentEvidenceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    evidence_type: str
    file_path: str
    file_name: str
    file_size: int
    mime_type: str
    verification_status: str
    verification_notes: Optional[str] = None
    created_at: datetime


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    incident_number: str
    title: str
    description: str
    category: str
    priority: str
    status: str
    latitude: float
    longitude: float
    address: str
    landmark: Optional[str] = None
    reported_by_id: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    confidence_score: float
    public_safety_risk: bool
    urgency_reason: Optional[str] = None
    is_duplicate: bool
    requires_human_approval: bool
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None


class IncidentDetailResponse(IncidentResponse):
    status_history: List[IncidentStatusHistoryResponse] = []
    evidences: List[IncidentEvidenceSummary] = []
    assigned_worker_id: Optional[str] = None
    assigned_worker_name: Optional[str] = None
    assignment_status: Optional[str] = None
