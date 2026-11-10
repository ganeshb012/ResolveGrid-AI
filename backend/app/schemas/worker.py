from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class WorkerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    full_name: str
    email: str
    phone: Optional[str] = None
    department_id: str
    department_name: Optional[str] = None
    employee_id: str
    skills: str
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    is_on_duty: bool
    availability_status: str = "AVAILABLE"  # AVAILABLE, BUSY, ON_BREAK, OFF_DUTY
    current_active_tasks: int
    created_at: datetime


class WorkerUpdateAvailability(BaseModel):
    status: str = Field(..., pattern="^(AVAILABLE|BUSY|ON_BREAK|OFF_DUTY)$")
    notes: Optional[str] = None


class WorkerLocationUpdate(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)


class AssignmentCreate(BaseModel):
    incident_id: str
    worker_id: str
    assigned_by_type: str = "ADMIN"


class AssignmentStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(ACCEPTED|REJECTED|IN_PROGRESS|COMPLETED)$")
    rejection_reason: Optional[str] = None
    worker_notes: Optional[str] = None


class AssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    incident_id: str
    incident_number: Optional[str] = None
    incident_title: Optional[str] = None
    incident_description: Optional[str] = None
    incident_category: Optional[str] = None
    incident_priority: Optional[str] = None
    incident_status: Optional[str] = None
    incident_latitude: Optional[float] = None
    incident_longitude: Optional[float] = None
    incident_address: Optional[str] = None
    worker_id: str
    worker_name: Optional[str] = None
    assigned_by_type: str
    status: str
    offered_at: datetime
    responded_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    worker_distance_km: Optional[float] = None
    worker_notes: Optional[str] = None
