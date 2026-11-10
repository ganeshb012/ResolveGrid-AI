import asyncio
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.entities import (
    Assignment, Incident, WorkerProfile, IncidentStatusHistory, User, utc_now
)
from backend.app.schemas.worker import (
    AssignmentCreate, AssignmentResponse, AssignmentStatusUpdate
)
from backend.app.api.deps import get_current_user, require_role
from backend.app.websockets.manager import ws_manager
from backend.app.agents.workflow import verification_node
from backend.app.agents.state import AgentState

router = APIRouter()


def serialize_assignment(a: Assignment) -> AssignmentResponse:
    inc = a.incident
    worker = a.worker
    return AssignmentResponse(
        id=a.id,
        incident_id=a.incident_id,
        incident_number=inc.incident_number if inc else None,
        incident_title=inc.title if inc else None,
        incident_description=inc.description if inc else None,
        incident_category=inc.category if inc else None,
        incident_priority=inc.priority if inc else None,
        incident_status=inc.status if inc else None,
        incident_latitude=inc.latitude if inc else None,
        incident_longitude=inc.longitude if inc else None,
        incident_address=inc.address if inc else None,
        worker_id=a.worker_id,
        worker_name=worker.user.full_name if (worker and worker.user) else None,
        assigned_by_type=a.assigned_by_type,
        status=a.status,
        offered_at=a.offered_at,
        responded_at=a.responded_at,
        rejection_reason=a.rejection_reason,
        started_at=a.started_at,
        completed_at=a.completed_at,
        worker_distance_km=a.worker_distance_km,
        worker_notes=a.worker_notes
    )


@router.post("", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    assign_in: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN"))
):
    incident = db.query(Incident).filter(Incident.id == assign_in.incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    worker = db.query(WorkerProfile).filter(WorkerProfile.id == assign_in.worker_id).first()
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")

    if incident.status in ["RESOLVED", "REJECTED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign worker to resolved or closed incident"
        )

    # Prevent duplicate active or completed assignments
    existing_active = db.query(Assignment).filter(
        Assignment.incident_id == assign_in.incident_id,
        Assignment.status.in_(["OFFERED", "ACCEPTED", "IN_PROGRESS", "COMPLETED"])
    ).first()
    if existing_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incident already has an active or completed worker assignment"
        )

    assignment = Assignment(
        id=str(uuid.uuid4()),
        incident_id=assign_in.incident_id,
        worker_id=assign_in.worker_id,
        assigned_by_type=assign_in.assigned_by_type,
        status="OFFERED",
        offered_at=utc_now()
    )
    db.add(assignment)

    worker.current_active_tasks += 1
    incident.status = "ASSIGNED"

    db.add(IncidentStatusHistory(
        id=str(uuid.uuid4()),
        incident_id=incident.id,
        old_status=incident.status,
        new_status="ASSIGNED",
        change_reason=f"Manually assigned by admin {current_user.full_name}",
        trigger_type="ADMIN",
        changed_by_id=current_user.id,
        timestamp=utc_now()
    ))
    db.commit()
    db.refresh(assignment)

    await ws_manager.broadcast("INCIDENT_ASSIGNED", {
        "incident_id": incident.id,
        "worker_id": worker.id,
        "assignment_id": assignment.id
    })

    return serialize_assignment(assignment)


@router.get("", response_model=List[AssignmentResponse])
async def list_assignments(
    worker_id: Optional[str] = None,
    incident_id: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN"))
):
    query = db.query(Assignment)
    if worker_id:
        query = query.filter(Assignment.worker_id == worker_id)
    if incident_id:
        query = query.filter(Assignment.incident_id == incident_id)
    if status_filter:
        query = query.filter(Assignment.status == status_filter)

    assignments = query.order_by(Assignment.created_at.desc()).all()
    return [serialize_assignment(a) for a in assignments]


@router.get("/my", response_model=List[AssignmentResponse])
async def list_my_assignments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("WORKER", "ADMIN"))
):
    worker = db.query(WorkerProfile).filter(WorkerProfile.user_id == current_user.id).first()
    if not worker:
        return []

    assignments = db.query(Assignment).filter(
        Assignment.worker_id == worker.id
    ).order_by(Assignment.created_at.desc()).all()

    return [serialize_assignment(a) for a in assignments]


@router.patch("/{assignment_id}", response_model=AssignmentResponse)
async def update_assignment_status(
    assignment_id: str,
    update_in: AssignmentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    # Only ADMIN or the assigned WORKER can update an assignment
    is_admin = current_user.role == "ADMIN"
    is_assigned_worker = (
        assignment.worker is not None and
        assignment.worker.user_id == current_user.id
    )
    if not (is_admin or is_assigned_worker):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to update this assignment"
        )

    old_status = assignment.status
    new_status = update_in.status

    # Prevent altering status of already completed assignment
    if old_status == "COMPLETED" and new_status != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot alter status of an already completed assignment"
        )

    assignment.status = new_status
    assignment.responded_at = utc_now()

    if update_in.rejection_reason:
        assignment.rejection_reason = update_in.rejection_reason
    if update_in.worker_notes:
        assignment.worker_notes = update_in.worker_notes

    incident = assignment.incident
    worker = assignment.worker

    if new_status == "ACCEPTED":
        if incident:
            incident.status = "IN_PROGRESS"
            db.add(IncidentStatusHistory(
                id=str(uuid.uuid4()),
                incident_id=incident.id,
                old_status="ASSIGNED",
                new_status="IN_PROGRESS",
                change_reason="Worker accepted assignment and dispatched to site",
                trigger_type="WORKER",
                changed_by_id=current_user.id,
                timestamp=utc_now()
            ))
        assignment.started_at = utc_now()

    elif new_status == "REJECTED":
        if worker and worker.current_active_tasks > 0:
            worker.current_active_tasks -= 1
        if incident:
            incident.status = "ESCALATED"
            incident.urgency_reason = f"Worker rejected: {update_in.rejection_reason or 'No reason provided'}"
            db.add(IncidentStatusHistory(
                id=str(uuid.uuid4()),
                incident_id=incident.id,
                old_status=incident.status,
                new_status="ESCALATED",
                change_reason=f"Worker rejected assignment: {update_in.rejection_reason}",
                trigger_type="WORKER",
                changed_by_id=current_user.id,
                timestamp=utc_now()
            ))

    elif new_status == "COMPLETED":
        assignment.completed_at = utc_now()
        if worker and worker.current_active_tasks > 0:
            worker.current_active_tasks -= 1

        if incident:
            incident.status = "RESOLVED_PENDING_VERIFICATION"
            db.add(IncidentStatusHistory(
                id=str(uuid.uuid4()),
                incident_id=incident.id,
                old_status="IN_PROGRESS",
                new_status="RESOLVED_PENDING_VERIFICATION",
                change_reason="Worker marked resolution complete; awaiting evidence verification",
                trigger_type="WORKER",
                changed_by_id=current_user.id,
                timestamp=utc_now()
            ))

    db.commit()
    db.refresh(assignment)

    await ws_manager.broadcast("ASSIGNMENT_UPDATED", {
        "assignment_id": assignment.id,
        "incident_id": assignment.incident_id,
        "status": new_status,
        "worker_name": current_user.full_name
    })

    # If marked COMPLETED, trigger Verification Agent workflow
    if new_status == "COMPLETED" and incident:
        from backend.app.agents.workflow import execute_verification_workflow
        await execute_verification_workflow(incident.id)

    return serialize_assignment(assignment)
