import asyncio
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.entities import AgentExecution, AgentAction, Incident, User
from backend.app.schemas.agent import (
    AgentExecutionResponse,
    AgentActionResponse,
    AgentRunRequest,
    AgentRunResponse,
)
from backend.app.agents.workflow import resolvegrid_workflow
from backend.app.agents.state import AgentState
from backend.app.api.deps import require_role

router = APIRouter()


@router.post("/run", response_model=AgentRunResponse)
async def run_agent_workflow(
    req: AgentRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN"))
):
    incident = db.query(Incident).filter(Incident.id == req.incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    workflow_run_id = f"manual_{uuid.uuid4().hex[:8]}"

    initial_state: AgentState = {
        "incident_id": incident.id,
        "workflow_run_id": workflow_run_id,
        "title": incident.title,
        "description": incident.description,
        "category": incident.category,
        "priority": incident.priority,
        "status": incident.status,
        "latitude": incident.latitude,
        "longitude": incident.longitude,
        "address": incident.address,
        "landmark": incident.landmark,
        "reported_by_id": incident.reported_by_id,
        "department_id": incident.department_id,
        "department_code": incident.department.code if incident.department else None,
        "assigned_worker_id": None,
        "assigned_worker_name": None,
        "worker_distance_km": None,
        "confidence_score": incident.confidence_score,
        "is_duplicate": False,
        "duplicate_of_id": None,
        "public_safety_risk": incident.public_safety_risk,
        "urgency_reason": incident.urgency_reason,
        "requires_human_approval": False,
        "approval_reason": None,
        "approval_id": None,
        "escalation_reason": None,
        "worker_notified": False,
        "citizen_notified": False,
        "worker_audio_url": None,
        "citizen_audio_url": None,
        "verification_passed": False,
        "verification_notes": None,
        "resolution_approved": False,
        "current_agent": "INCIDENT_INTELLIGENCE",
        "completed_agents": [],
        "actions_taken": [],
        "logs": [],
        "errors": []
    }

    # Execute workflow
    result = await resolvegrid_workflow.ainvoke(initial_state)

    return AgentRunResponse(
        workflow_run_id=workflow_run_id,
        incident_id=incident.id,
        status=result.get("status", "COMPLETED"),
        completed_agents=result.get("completed_agents", []),
        actions_taken=result.get("actions_taken", []),
        requires_approval=result.get("requires_human_approval", False),
        summary=f"Processed by {len(result.get('completed_agents', []))} agents. Current status: {result.get('status')}"
    )


@router.get("/activity", response_model=List[AgentExecutionResponse])
async def list_agent_activity(
    incident_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN"))
):
    query = db.query(AgentExecution)
    if incident_id:
        query = query.filter(AgentExecution.incident_id == incident_id)
    if agent_name:
        if agent_name in ["PRIORITY", "PRIORITY_ASSESSMENT"]:
            query = query.filter(AgentExecution.agent_name.in_(["PRIORITY", "PRIORITY_ASSESSMENT"]))
        elif agent_name == "INCIDENT_INTELLIGENCE":
            query = query.filter(AgentExecution.agent_name.in_(["INCIDENT_INTELLIGENCE", "DUPLICATE_DETECTION"]))
        else:
            query = query.filter(AgentExecution.agent_name == agent_name)

    executions = query.order_by(AgentExecution.started_at.desc()).limit(limit).all()

    results = []
    for ex in executions:
        actions = db.query(AgentAction).filter(
            AgentAction.agent_execution_id == ex.id
        ).order_by(AgentAction.executed_at.asc()).all()

        results.append(AgentExecutionResponse(
            id=ex.id,
            incident_id=ex.incident_id,
            workflow_run_id=ex.workflow_run_id,
            agent_name=ex.agent_name,
            status=ex.status,
            input_payload=ex.input_payload,
            output_payload=ex.output_payload,
            reasoning_summary=ex.reasoning_summary,
            error_message=ex.error_message,
            retry_count=ex.retry_count,
            latency_ms=ex.latency_ms,
            started_at=ex.started_at,
            completed_at=ex.completed_at,
            actions=[AgentActionResponse.model_validate(a) for a in actions]
        ))

    return results


@router.get("/executions/{execution_id}", response_model=AgentExecutionResponse)
async def get_execution_detail(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN"))
):
    ex = db.query(AgentExecution).filter(AgentExecution.id == execution_id).first()
    if not ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent execution record not found")

    actions = db.query(AgentAction).filter(
        AgentAction.agent_execution_id == ex.id
    ).order_by(AgentAction.executed_at.asc()).all()

    return AgentExecutionResponse(
        id=ex.id,
        incident_id=ex.incident_id,
        workflow_run_id=ex.workflow_run_id,
        agent_name=ex.agent_name,
        status=ex.status,
        input_payload=ex.input_payload,
        output_payload=ex.output_payload,
        reasoning_summary=ex.reasoning_summary,
        error_message=ex.error_message,
        retry_count=ex.retry_count,
        latency_ms=ex.latency_ms,
        started_at=ex.started_at,
        completed_at=ex.completed_at,
        actions=[AgentActionResponse.model_validate(a) for a in actions]
    )
