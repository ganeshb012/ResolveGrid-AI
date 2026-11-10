from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class HumanApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    incident_id: str
    incident_number: Optional[str] = None
    incident_title: Optional[str] = None
    incident_priority: Optional[str] = None
    agent_execution_id: Optional[str] = None
    approval_type: str
    requested_by_agent: str
    reason: str
    context_data: Optional[str] = None
    status: str
    reviewer_id: Optional[str] = None
    reviewer_name: Optional[str] = None
    review_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime


class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(..., pattern="^(APPROVE|REJECT)$")
    review_notes: Optional[str] = None
