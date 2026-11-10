from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class AgentState(TypedDict):
    # Workflow identifiers
    incident_id: str
    workflow_run_id: str

    # Incident information
    title: str
    description: str
    category: str
    priority: str
    status: str
    latitude: float
    longitude: float
    address: str
    landmark: Optional[str]
    reported_by_id: Optional[str]

    # Department & Worker assignment
    department_id: Optional[str]
    department_code: Optional[str]
    assigned_worker_id: Optional[str]
    assigned_worker_name: Optional[str]
    worker_distance_km: Optional[float]

    # Intelligence & Priority metrics
    confidence_score: float
    is_duplicate: bool
    duplicate_of_id: Optional[str]
    public_safety_risk: bool
    urgency_reason: Optional[str]

    # Approvals & Escalation
    requires_human_approval: bool
    approval_reason: Optional[str]
    approval_id: Optional[str]
    escalation_reason: Optional[str]

    # Coordination & Communication
    worker_notified: bool
    citizen_notified: bool
    worker_audio_url: Optional[str]
    citizen_audio_url: Optional[str]

    # Verification
    verification_passed: bool
    verification_notes: Optional[str]
    resolution_approved: bool

    # Audit & telemetry
    current_agent: str
    completed_agents: List[str]
    actions_taken: List[str]
    logs: List[Dict[str, Any]]
    errors: List[str]
