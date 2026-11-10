from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    incident_id: str
    assignment_id: Optional[str] = None
    uploaded_by_id: str
    uploaded_by_name: Optional[str] = None
    evidence_type: str
    file_path: str
    file_name: str
    file_size: int
    mime_type: str
    verification_status: str
    verification_notes: Optional[str] = None
    created_at: datetime


class EvidenceVerifyRequest(BaseModel):
    verification_status: str = Field(..., pattern="^(ACCEPTED|REJECTED)$")
    verification_notes: Optional[str] = None
