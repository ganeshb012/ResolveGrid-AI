from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class AgentActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tool_name: str
    tool_input: Optional[str] = None
    tool_output: Optional[str] = None
    status: str
    executed_at: datetime


class AgentExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    incident_id: str
    workflow_run_id: str
    agent_name: str
    status: str
    input_payload: Optional[str] = None
    output_payload: Optional[str] = None
    reasoning_summary: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int
    latency_ms: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    actions: List[AgentActionResponse] = []


class AgentRunRequest(BaseModel):
    incident_id: str
    trigger_reason: Optional[str] = "Manual admin trigger"


class AgentRunResponse(BaseModel):
    workflow_run_id: str
    incident_id: str
    status: str
    completed_agents: List[str]
    actions_taken: List[str]
    requires_approval: bool
    summary: str


class WorkflowStateSchema(BaseModel):
    incident_id: str
    title: str
    description: str
    category: str
    priority: str
    status: str
    latitude: float
    longitude: float
    address: str
    department_id: Optional[str] = None
    assigned_worker_id: Optional[str] = None
    is_duplicate: bool = False
    duplicate_of_id: Optional[str] = None
    confidence_score: float = 1.0
    public_safety_risk: bool = False
    requires_human_approval: bool = False
    approval_reason: Optional[str] = None
    escalation_reason: Optional[str] = None
    verification_passed: bool = False
    worker_notified: bool = False
    citizen_notified: bool = False
    workflow_run_id: str
    logs: List[Dict[str, Any]] = []
