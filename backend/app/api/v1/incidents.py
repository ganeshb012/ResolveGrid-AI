import asyncio
import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.models.entities import (
    Incident,
    IncidentReport,
    IncidentStatusHistory,
    IncidentEvidence,
    Department,
    User,
    Assignment,
    utc_now,
)
from backend.app.schemas.incident import (
    IncidentCreate,
    IncidentUpdate,
    IncidentResponse,
    IncidentDetailResponse,
    IncidentStatusHistoryResponse,
    IncidentEvidenceSummary,
)
from backend.app.schemas.evidence import EvidenceResponse
from backend.app.api.deps import get_current_user, get_current_user_optional, require_role
from backend.app.agents.workflow import resolvegrid_workflow
from backend.app.agents.state import AgentState
from backend.app.websockets.manager import ws_manager
from backend.app.integrations.storage.local import storage

router = APIRouter()


@router.post("", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(
    incident_in: IncidentCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    incident_num = f"INC-{uuid.uuid4().hex[:8].upper()}"

    incident = Incident(
        id=str(uuid.uuid4()),
        incident_number=incident_num,
        title=incident_in.title,
        description=incident_in.description,
        category=incident_in.category or "OTHER",
        priority=incident_in.priority or "MEDIUM",
        status="REPORTED",
        latitude=incident_in.latitude,
        longitude=incident_in.longitude,
        address=incident_in.address,
        landmark=incident_in.landmark,
        reported_by_id=current_user.id if current_user else None,
        confidence_score=1.0,
        public_safety_risk=False,
        is_duplicate=False,
        requires_human_approval=False,
        created_at=utc_now()
    )
    db.add(incident)
    db.flush()

    # Save initial report
    report = IncidentReport(
        id=str(uuid.uuid4()),
        incident_id=incident.id,
        citizen_id=current_user.id if current_user else None,
        source=incident_in.source,
        original_text=incident_in.description,
        raw_audio_path=incident_in.original_audio_path,
        language_detected=incident_in.language or "en",
        created_at=utc_now()
    )
    db.add(report)

    # Initial status history
    history = IncidentStatusHistory(
        id=str(uuid.uuid4()),
        incident_id=incident.id,
        old_status=None,
        new_status="REPORTED",
        changed_by_id=current_user.id if current_user else None,
        change_reason="Complaint submitted by citizen",
        trigger_type="CITIZEN",
        timestamp=utc_now()
    )
    db.add(history)
    db.commit()
    db.refresh(incident)

    # Broadcast new incident via WebSocket
    await ws_manager.broadcast("NEW_INCIDENT", {
        "incident_id": incident.id,
        "incident_number": incident.incident_number,
        "title": incident.title,
        "category": incident.category,
        "priority": incident.priority,
        "latitude": incident.latitude,
        "longitude": incident.longitude,
        "address": incident.address
    })

    # Trigger LangGraph Multi-Agent Workflow asynchronously
    workflow_run_id = f"run_{uuid.uuid4().hex[:10]}"
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
        "department_id": None,
        "department_code": None,
        "assigned_worker_id": None,
        "assigned_worker_name": None,
        "worker_distance_km": None,
        "confidence_score": 1.0,
        "is_duplicate": False,
        "duplicate_of_id": None,
        "public_safety_risk": False,
        "urgency_reason": None,
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

    asyncio.create_task(resolvegrid_workflow.ainvoke(initial_state))

    return incident


@router.get("", response_model=List[IncidentResponse])
async def list_incidents(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority_filter: Optional[str] = Query(None, alias="priority"),
    category_filter: Optional[str] = Query(None, alias="category"),
    department_id: Optional[str] = None,
    mine: bool = False,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    if mine and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to view personal complaints"
        )

    query = db.query(Incident)

    if mine and current_user:
        query = query.filter(Incident.reported_by_id == current_user.id)
    if status_filter:
        query = query.filter(Incident.status == status_filter)
    if priority_filter:
        query = query.filter(Incident.priority == priority_filter)
    if category_filter:
        query = query.filter(Incident.category == category_filter)
    if department_id:
        query = query.filter(Incident.department_id == department_id)
    if search:
        search_fmt = f"%{search}%"
        query = query.filter(
            (Incident.title.ilike(search_fmt)) |
            (Incident.description.ilike(search_fmt)) |
            (Incident.incident_number.ilike(search_fmt)) |
            (Incident.address.ilike(search_fmt))
        )

    incidents = query.order_by(Incident.created_at.desc()).all()

    # Populate department name
    results = []
    for inc in incidents:
        dept_name = inc.department.name if inc.department else None
        inc_dict = IncidentResponse.model_validate(inc).model_dump()
        inc_dict["department_name"] = dept_name
        results.append(IncidentResponse(**inc_dict))

    return results


@router.get("/{incident_id}", response_model=IncidentDetailResponse)
async def get_incident(incident_id: str, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    history_records = db.query(IncidentStatusHistory).filter(
        IncidentStatusHistory.incident_id == incident_id
    ).order_by(IncidentStatusHistory.timestamp.asc()).all()

    evidences = db.query(IncidentEvidence).filter(
        IncidentEvidence.incident_id == incident_id
    ).order_by(IncidentEvidence.created_at.desc()).all()

    # Get active or latest assignment
    assignment = db.query(Assignment).filter(
        Assignment.incident_id == incident_id
    ).order_by(Assignment.created_at.desc()).first()

    assigned_worker_id = None
    assigned_worker_name = None
    assignment_status = None
    if assignment:
        assigned_worker_id = assignment.worker_id
        assignment_status = assignment.status
        if assignment.worker and assignment.worker.user:
            assigned_worker_name = assignment.worker.user.full_name

    resp_data = IncidentResponse.model_validate(incident).model_dump()
    resp_data["department_name"] = incident.department.name if incident.department else None

    return IncidentDetailResponse(
        **resp_data,
        status_history=[IncidentStatusHistoryResponse.model_validate(h) for h in history_records],
        evidences=[IncidentEvidenceSummary.model_validate(e) for e in evidences],
        assigned_worker_id=assigned_worker_id,
        assigned_worker_name=assigned_worker_name,
        assignment_status=assignment_status
    )


@router.patch("/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: str,
    update_data: IncidentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN"))
):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    old_status = incident.status
    if update_data.status and update_data.status != old_status:
        incident.status = update_data.status
        if update_data.status == "RESOLVED":
            incident.resolved_at = utc_now()

        history = IncidentStatusHistory(
            id=str(uuid.uuid4()),
            incident_id=incident.id,
            old_status=old_status,
            new_status=update_data.status,
            changed_by_id=current_user.id,
            change_reason="Updated via API",
            trigger_type=current_user.role,
            timestamp=utc_now()
        )
        db.add(history)

    if update_data.priority:
        incident.priority = update_data.priority
    if update_data.category:
        incident.category = update_data.category
    if update_data.department_id:
        incident.department_id = update_data.department_id
    if update_data.landmark:
        incident.landmark = update_data.landmark
    if update_data.requires_human_approval is not None:
        incident.requires_human_approval = update_data.requires_human_approval

    db.commit()
    db.refresh(incident)

    await ws_manager.broadcast("INCIDENT_UPDATED", {
        "incident_id": incident.id,
        "status": incident.status,
        "priority": incident.priority
    })

    return incident


@router.get("/{incident_id}/history", response_model=List[IncidentStatusHistoryResponse])
async def get_incident_history(incident_id: str, db: Session = Depends(get_db)):
    history = db.query(IncidentStatusHistory).filter(
        IncidentStatusHistory.incident_id == incident_id
    ).order_by(IncidentStatusHistory.timestamp.asc()).all()
    return history


@router.post("/{incident_id}/evidence", response_model=EvidenceResponse)
async def upload_incident_evidence(
    incident_id: str,
    file: UploadFile = File(...),
    evidence_type: str = Form("PHOTO_AFTER"),
    notes: Optional[str] = Form(None),
    assignment_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    # Validate file extension and MIME type
    ext = Path(file.filename or "").suffix.lower()
    allowed_exts = {".jpg", ".jpeg", ".png", ".webp", ".wav", ".mp3", ".ogg"}
    content_type = (file.content_type or "").lower()
    if content_type not in (settings.ALLOWED_IMAGE_TYPES + settings.ALLOWED_AUDIO_TYPES) and ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed image/audio formats only."
        )

    # Validate file size if available from headers
    if file.size and file.size > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum allowed upload size of {settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB"
        )

    # Save file using local storage provider
    rel_path = await storage.save_file(
        file.file,
        file.filename,
        file.content_type or "application/octet-stream",
        subfolder="evidence"
    )

    evidence = IncidentEvidence(
        id=str(uuid.uuid4()),
        incident_id=incident_id,
        assignment_id=assignment_id,
        uploaded_by_id=current_user.id if current_user else None,
        evidence_type=evidence_type,
        file_path=rel_path,
        file_name=file.filename,
        file_size=file.size or 0,
        mime_type=file.content_type or "application/octet-stream",
        verification_status="PENDING",
        verification_notes=notes,
        created_at=utc_now()
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    await ws_manager.broadcast("EVIDENCE_SUBMITTED", {
        "incident_id": incident_id,
        "evidence_id": evidence.id,
        "evidence_type": evidence_type
    })

    # If resolution evidence is submitted and assignment is completed or pending verification, invoke Verification Agent
    if evidence_type == "PHOTO_AFTER":
        completed_assignment = db.query(Assignment).filter(
            Assignment.incident_id == incident_id,
            Assignment.status == "COMPLETED"
        ).first()
        if completed_assignment or incident.status == "RESOLVED_PENDING_VERIFICATION":
            from backend.app.agents.workflow import execute_verification_workflow
            await execute_verification_workflow(incident_id)

    return evidence


@router.post("/{incident_id}/verify")
async def trigger_verification(
    incident_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "WORKER"))
):
    """Explicitly trigger Verification Agent audit for an incident."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    from backend.app.agents.workflow import execute_verification_workflow
    result = await execute_verification_workflow(incident_id)
    return result


@router.get("/{incident_id}/evidence", response_model=List[EvidenceResponse])
async def list_incident_evidence(incident_id: str, db: Session = Depends(get_db)):
    evidences = db.query(IncidentEvidence).filter(
        IncidentEvidence.incident_id == incident_id
    ).order_by(IncidentEvidence.created_at.desc()).all()
    return evidences
