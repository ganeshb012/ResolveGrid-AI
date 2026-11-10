import asyncio
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.entities import HumanApproval, Incident, IncidentStatusHistory, User, utc_now
from backend.app.schemas.approval import HumanApprovalResponse, ApprovalDecisionRequest
from backend.app.api.deps import require_role
from backend.app.websockets.manager import ws_manager
from backend.app.agents.workflow import resume_workflow_from_resource_allocation

router = APIRouter()


def serialize_approval(appr: HumanApproval) -> HumanApprovalResponse:
    inc = appr.incident
    reviewer = appr.reviewer
    return HumanApprovalResponse(
        id=appr.id,
        incident_id=appr.incident_id,
        incident_number=inc.incident_number if inc else None,
        incident_title=inc.title if inc else None,
        incident_priority=inc.priority if inc else None,
        agent_execution_id=appr.agent_execution_id,
        approval_type=appr.approval_type,
        requested_by_agent=appr.requested_by_agent,
        reason=appr.reason,
        context_data=appr.context_data,
        status=appr.status,
        reviewer_id=appr.reviewer_id,
        reviewer_name=reviewer.full_name if reviewer else None,
        review_notes=appr.review_notes,
        reviewed_at=appr.reviewed_at,
        created_at=appr.created_at
    )


@router.get("", response_model=List[HumanApprovalResponse])
async def list_approvals(
    status_filter: Optional[str] = Query("PENDING", alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN"))
):
    query = db.query(HumanApproval)
    if status_filter:
        query = query.filter(HumanApproval.status == status_filter)

    approvals = query.order_by(HumanApproval.created_at.desc()).all()
    return [serialize_approval(a) for a in approvals]


@router.post("/{approval_id}/approve", response_model=HumanApprovalResponse)
async def approve_request(
    approval_id: str,
    req: ApprovalDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN"))
):
    approval = db.query(HumanApproval).filter(HumanApproval.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")

    if approval.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Approval request has already been decided: {approval.status}"
        )

    approval.status = "APPROVED"
    approval.reviewer_id = current_user.id
    approval.review_notes = req.review_notes
    approval.reviewed_at = utc_now()

    incident = approval.incident
    should_resume_allocation = False

    if incident:
        incident.requires_human_approval = False
        if approval.approval_type in ["UNCERTAIN_VERIFICATION", "INCIDENT_CLOSURE"]:
            incident.status = "RESOLVED"
            incident.resolved_at = utc_now()
        elif incident.status == "PENDING_APPROVAL" or approval.approval_type in [
            "CRITICAL_HAZARD", "HIGH_PRIORITY_ESCALATION", "UNUSUAL_RESOURCE_ALLOCATION"
        ]:
            incident.status = "CLASSIFIED"
            should_resume_allocation = True

        db.add(IncidentStatusHistory(
            id=str(uuid.uuid4()),
            incident_id=incident.id,
            old_status="PENDING_APPROVAL",
            new_status=incident.status,
            change_reason=f"Approved by Admin {current_user.full_name}: {req.review_notes or 'Approval granted'}",
            trigger_type="ADMIN",
            changed_by_id=current_user.id,
            timestamp=utc_now()
        ))

    db.commit()
    db.refresh(approval)

    await ws_manager.broadcast("APPROVAL_DECIDED", {
        "approval_id": approval.id,
        "incident_id": approval.incident_id,
        "decision": "APPROVED",
        "reviewer": current_user.full_name
    })

    # Asynchronously resume multi-agent workflow from Resource Allocation
    if should_resume_allocation and incident:
        asyncio.create_task(resume_workflow_from_resource_allocation(incident.id))

    return serialize_approval(approval)


@router.post("/{approval_id}/reject", response_model=HumanApprovalResponse)
async def reject_request(
    approval_id: str,
    req: ApprovalDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN"))
):
    approval = db.query(HumanApproval).filter(HumanApproval.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")

    if approval.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Approval request has already been decided: {approval.status}"
        )

    approval.status = "REJECTED"
    approval.reviewer_id = current_user.id
    approval.review_notes = req.review_notes
    approval.reviewed_at = utc_now()

    incident = approval.incident
    if incident:
        incident.requires_human_approval = False
        incident.status = "REJECTED"

        db.add(IncidentStatusHistory(
            id=str(uuid.uuid4()),
            incident_id=incident.id,
            old_status="PENDING_APPROVAL",
            new_status="REJECTED",
            change_reason=f"Approval rejected by Admin {current_user.full_name}: {req.review_notes or 'Rejected'}",
            trigger_type="ADMIN",
            changed_by_id=current_user.id,
            timestamp=utc_now()
        ))

    db.commit()
    db.refresh(approval)

    await ws_manager.broadcast("APPROVAL_DECIDED", {
        "approval_id": approval.id,
        "incident_id": approval.incident_id,
        "decision": "REJECTED",
        "reviewer": current_user.full_name
    })

    return serialize_approval(approval)
