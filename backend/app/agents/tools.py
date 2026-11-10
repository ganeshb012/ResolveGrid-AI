import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.models.entities import (
    Incident,
    IncidentReport,
    Department,
    WorkerProfile,
    WorkerAvailability,
    Assignment,
    IncidentEvidence,
    AgentAction,
    AgentExecution,
    IncidentStatusHistory,
    Notification,
    HumanApproval,
    User,
    utc_now,
)
from backend.app.services.distance_service import haversine_distance
from backend.app.websockets.manager import ws_manager
from backend.app.integrations.gnani.evon import EvonReasoningAdapter
from backend.app.integrations.gnani.timbre import TimbreTTSAdapter
from backend.app.integrations.gnani.schemas import EvonPromptRequest, TimbreSynthesizeRequest

logger = logging.getLogger("resolvegrid.agents.tools")


def log_tool_action(
    db: Session,
    agent_execution_id: Optional[str],
    incident_id: Optional[str],
    tool_name: str,
    tool_input: Any,
    tool_output: Any,
    status: str = "SUCCESS"
) -> str:
    # Validate foreign keys exist in DB before attaching
    valid_exec_id = None
    if agent_execution_id:
        exists_exec = db.query(AgentExecution).filter(AgentExecution.id == agent_execution_id).first()
        if exists_exec:
            valid_exec_id = agent_execution_id

    valid_inc_id = None
    if incident_id and incident_id != "SYSTEM":
        exists_inc = db.query(Incident).filter(Incident.id == incident_id).first()
        if exists_inc:
            valid_inc_id = incident_id

    action = AgentAction(
        id=str(uuid.uuid4()),
        agent_execution_id=valid_exec_id,
        incident_id=valid_inc_id,
        tool_name=tool_name,
        tool_input=json.dumps(tool_input) if not isinstance(tool_input, str) else tool_input,
        tool_output=json.dumps(tool_output) if not isinstance(tool_output, str) else tool_output,
        status=status,
        executed_at=utc_now()
    )
    db.add(action)
    db.commit()
    return action.id


async def find_similar_incidents(
    db: Session,
    incident_id: str,
    lat: float,
    lon: float,
    category: str,
    radius_km: float = 0.25,
    agent_execution_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Check for nearby open incidents of the same category to prevent duplicate work."""
    candidates = db.query(Incident).filter(
        Incident.id != incident_id,
        Incident.category == category,
        Incident.status.notin_(["RESOLVED", "REJECTED"]),
        Incident.is_duplicate == False
    ).all()

    for cand in candidates:
        dist = haversine_distance(lat, lon, cand.latitude, cand.longitude)
        if dist <= radius_km:
            log_tool_action(
                db, agent_execution_id, incident_id,
                "find_similar_incidents",
                {"lat": lat, "lon": lon, "category": category, "radius_km": radius_km},
                {"duplicate_found": True, "duplicate_of_id": cand.id, "distance_km": dist}
            )
            return {"duplicate_of_id": cand.id, "incident_number": cand.incident_number, "distance_km": dist}

    log_tool_action(
        db, agent_execution_id, incident_id,
        "find_similar_incidents",
        {"lat": lat, "lon": lon, "category": category},
        {"duplicate_found": False}
    )
    return None


async def classify_incident(
    db: Session,
    incident_id: str,
    text: str,
    agent_execution_id: Optional[str] = None
) -> Dict[str, Any]:
    """Classify incident type and extract department and risk factors using Gnani Evon."""
    evon = EvonReasoningAdapter()
    res = await evon.generate_reasoning(EvonPromptRequest(
        prompt=text,
        system_instruction="Classify public infrastructure incident and extract structured categories."
    ))

    data = res.structured_data or {}
    category = data.get("category", "OTHER")
    dept_code = data.get("responsible_department_code", "GENERAL")
    public_safety = bool(data.get("public_safety_risk", False))
    urgency_reason = data.get("urgency_reason", "Assessed by Evon reasoning engine.")

    # Find department in DB
    dept = db.query(Department).filter(Department.code == dept_code).first()
    dept_id = dept.id if dept else None

    # Update incident record
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if incident:
        incident.category = category
        incident.department_id = dept_id
        incident.public_safety_risk = public_safety
        incident.urgency_reason = urgency_reason
        incident.confidence_score = float(data.get("confidence", 0.95))
        db.commit()

    log_tool_action(
        db, agent_execution_id, incident_id,
        "classify_incident",
        {"text": text[:100]},
        {"category": category, "department_code": dept_code, "safety_risk": public_safety}
    )

    return {
        "category": category,
        "department_id": dept_id,
        "department_code": dept_code,
        "public_safety_risk": public_safety,
        "urgency_reason": urgency_reason,
        "confidence_score": 0.95,
        "reasoning": res.reasoning_summary
    }


async def calculate_priority(
    db: Session,
    incident_id: str,
    category: str,
    public_safety_risk: bool,
    description: str,
    agent_execution_id: Optional[str] = None
) -> Dict[str, Any]:
    """Assess severity and calculate priority level: CRITICAL, HIGH, MEDIUM, LOW."""
    desc_lower = description.lower()
    requires_approval = False

    if public_safety_risk or category == "OPEN_MANHOLE" or any(w in desc_lower for w in ["burst", "emergency", "fatal", "flood"]):
        priority = "CRITICAL"
        requires_approval = True  # Critical escalations require admin oversight
        urgency_explanation = "Immediate hazard to public safety and high likelihood of vehicle accidents or injuries."
    elif category in ["WATER_LEAKAGE", "ROAD_POTHOLE"] or any(w in desc_lower for w in ["huge", "heavy", "damage"]):
        priority = "HIGH"
        urgency_explanation = "Significant public inconvenience with rapid compounding damage risk."
    elif category in ["GARBAGE_OVERFLOW", "STREETLIGHT"]:
        priority = "MEDIUM"
        urgency_explanation = "Standard service disruption; prioritized for standard municipal routing."
    else:
        priority = "LOW"
        urgency_explanation = "Non-hazardous general municipal infrastructure maintenance."

    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if incident:
        incident.priority = priority
        incident.requires_human_approval = requires_approval
        db.commit()

    log_tool_action(
        db, agent_execution_id, incident_id,
        "calculate_priority",
        {"category": category, "safety_risk": public_safety_risk},
        {"priority": priority, "requires_approval": requires_approval, "reason": urgency_explanation}
    )

    return {
        "priority": priority,
        "requires_human_approval": requires_approval,
        "urgency_explanation": urgency_explanation
    }


async def get_available_workers(
    db: Session,
    department_id: Optional[str],
    incident_lat: float,
    incident_lon: float,
    max_distance_km: float = 30.0,
    agent_execution_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieve on-duty available workers ordered by proximity using Haversine calculation."""
    query = db.query(WorkerProfile).filter(
        WorkerProfile.is_on_duty == True,
        WorkerProfile.current_active_tasks < 3
    )
    if department_id:
        query = query.filter(WorkerProfile.department_id == department_id)

    workers = query.all()
    ranked = []

    for w in workers:
        w_lat = w.current_latitude or 18.5204  # Default Pune central if unset
        w_lon = w.current_longitude or 73.8567
        dist = haversine_distance(incident_lat, incident_lon, w_lat, w_lon)

        # Worker availability check
        latest_avail = db.query(WorkerAvailability).filter(
            WorkerAvailability.worker_id == w.id
        ).order_by(WorkerAvailability.updated_at.desc()).first()

        status = latest_avail.status if latest_avail else "AVAILABLE"
        if status in ["AVAILABLE", "BUSY"] and dist <= max_distance_km:
            ranked.append({
                "worker_id": w.id,
                "user_id": w.user_id,
                "full_name": w.user.full_name if w.user else "Municipal Worker",
                "phone": w.user.phone if w.user else None,
                "distance_km": dist,
                "active_tasks": w.current_active_tasks,
                "status": status,
                "score": dist + (w.current_active_tasks * 2.0)  # Lower is better
            })

    ranked.sort(key=lambda x: x["score"])

    log_tool_action(
        db, agent_execution_id, "SYSTEM",
        "get_available_workers",
        {"dept_id": department_id, "lat": incident_lat, "lon": incident_lon},
        {"candidates_count": len(ranked), "best_worker_id": ranked[0]["worker_id"] if ranked else None}
    )

    return ranked


async def assign_worker(
    db: Session,
    incident_id: str,
    worker_id: str,
    distance_km: float,
    assigned_by_type: str = "AGENT",
    agent_execution_id: Optional[str] = None
) -> Dict[str, Any]:
    """Assign an incident to a worker, update task counts, and record assignment status."""
    assignment = Assignment(
        id=str(uuid.uuid4()),
        incident_id=incident_id,
        worker_id=worker_id,
        assigned_by_type=assigned_by_type,
        status="OFFERED",
        worker_distance_km=distance_km,
        offered_at=utc_now()
    )
    db.add(assignment)

    # Update worker profile active tasks
    worker = db.query(WorkerProfile).filter(WorkerProfile.id == worker_id).first()
    if worker:
        worker.current_active_tasks += 1

    # Update incident status
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if incident:
        incident.status = "ASSIGNED"
        db.add(IncidentStatusHistory(
            incident_id=incident.id,
            old_status="CLASSIFIED",
            new_status="ASSIGNED",
            change_reason=f"Assigned to {worker.user.full_name if worker and worker.user else 'worker'} ({distance_km:.1f} km away)",
            trigger_type=assigned_by_type
        ))

    db.commit()

    log_tool_action(
        db, agent_execution_id, incident_id,
        "assign_worker",
        {"worker_id": worker_id, "distance_km": distance_km, "assigned_by": assigned_by_type},
        {"assignment_id": assignment.id, "status": "OFFERED"}
    )

    await ws_manager.broadcast("INCIDENT_ASSIGNED", {
        "incident_id": incident_id,
        "worker_id": worker_id,
        "assignment_id": assignment.id,
        "distance_km": distance_km
    })

    return {"assignment_id": assignment.id, "status": "OFFERED"}


async def notify_worker(
    db: Session,
    worker_id: str,
    incident_id: str,
    assignment_id: str,
    message: str,
    language: str = "en",
    agent_execution_id: Optional[str] = None
) -> Dict[str, Any]:
    """Generate voice instructions via Timbre and notify the assigned field worker."""
    worker = db.query(WorkerProfile).filter(WorkerProfile.id == worker_id).first()
    if not worker or not worker.user:
        return {"status": "FAILED", "reason": "Worker user record not found"}

    tts = TimbreTTSAdapter()
    audio_url = None
    try:
        synth = await tts.synthesize(TimbreSynthesizeRequest(
            text=message,
            language=language
        ))
        audio_url = synth.audio_url
    except Exception as e:
        logger.warning("Voice synthesis failed for worker notification: %s", str(e))

    notification = Notification(
        id=str(uuid.uuid4()),
        recipient_id=worker.user.id,
        incident_id=incident_id,
        channel="VOICE_TIMBRE" if audio_url else "IN_APP",
        title="Immediate Task Assignment",
        message=message,
        audio_file_path=audio_url,
        language=language,
        status="SENT",
        sent_at=utc_now()
    )
    db.add(notification)
    db.commit()

    log_tool_action(
        db, agent_execution_id, incident_id,
        "notify_worker",
        {"worker_id": worker_id, "channel": "VOICE_TIMBRE", "language": language},
        {"notification_id": notification.id, "audio_url": audio_url}
    )

    await ws_manager.send_to_user(
        worker.user.id,
        "NEW_TASK_ASSIGNMENT",
        {
            "assignment_id": assignment_id,
            "incident_id": incident_id,
            "message": message,
            "audio_url": audio_url
        }
    )

    return {"status": "SENT", "audio_url": audio_url}


async def notify_citizen(
    db: Session,
    incident_id: str,
    citizen_id: Optional[str],
    title: str,
    message: str,
    language: str = "en",
    agent_execution_id: Optional[str] = None
) -> Dict[str, Any]:
    """Synthesize voice update with Timbre and push notification to the reporting citizen."""
    if not citizen_id:
        return {"status": "SKIPPED", "reason": "No citizen account linked"}

    tts = TimbreTTSAdapter()
    audio_url = None
    try:
        synth = await tts.synthesize(TimbreSynthesizeRequest(
            text=message,
            language=language
        ))
        audio_url = synth.audio_url
    except Exception as e:
        logger.warning("Voice synthesis failed for citizen notification: %s", str(e))

    notification = Notification(
        id=str(uuid.uuid4()),
        recipient_id=citizen_id,
        incident_id=incident_id,
        channel="VOICE_TIMBRE" if audio_url else "IN_APP",
        title=title,
        message=message,
        audio_file_path=audio_url,
        language=language,
        status="SENT",
        sent_at=utc_now()
    )
    db.add(notification)
    db.commit()

    log_tool_action(
        db, agent_execution_id, incident_id,
        "notify_citizen",
        {"citizen_id": citizen_id, "title": title, "channel": "VOICE_TIMBRE"},
        {"notification_id": notification.id, "audio_url": audio_url}
    )

    await ws_manager.send_to_user(
        citizen_id,
        "INCIDENT_UPDATE",
        {
            "incident_id": incident_id,
            "title": title,
            "message": message,
            "audio_url": audio_url
        }
    )

    return {"status": "SENT", "audio_url": audio_url}


async def update_incident_status(
    db: Session,
    incident_id: str,
    new_status: str,
    reason: str,
    trigger_type: str = "AGENT",
    changed_by_id: Optional[str] = None,
    agent_execution_id: Optional[str] = None
) -> Dict[str, Any]:
    """Atomically transition incident status and record audit history."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        return {"status": "FAILED", "reason": "Incident not found"}

    old_status = incident.status
    incident.status = new_status
    if new_status == "RESOLVED":
        incident.resolved_at = utc_now()

    history = IncidentStatusHistory(
        id=str(uuid.uuid4()),
        incident_id=incident_id,
        old_status=old_status,
        new_status=new_status,
        change_reason=reason,
        trigger_type=trigger_type,
        changed_by_id=changed_by_id,
        timestamp=utc_now()
    )
    db.add(history)
    db.commit()

    log_tool_action(
        db, agent_execution_id, incident_id,
        "update_incident_status",
        {"old_status": old_status, "new_status": new_status, "reason": reason},
        {"success": True}
    )

    await ws_manager.broadcast("INCIDENT_STATUS_CHANGED", {
        "incident_id": incident_id,
        "old_status": old_status,
        "new_status": new_status,
        "reason": reason
    })

    return {"success": True, "old_status": old_status, "new_status": new_status}


async def verify_resolution(
    db: Session,
    incident_id: str,
    agent_execution_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Verification Agent evaluates worker completion evidence:
    Requires at least one photo after completion, completed assignment status, and worker notes.
    """
    evidences = db.query(IncidentEvidence).filter(
        IncidentEvidence.incident_id == incident_id,
        IncidentEvidence.evidence_type.in_(["PHOTO_AFTER", "PHOTO_BEFORE"])
    ).all()

    assignment = db.query(Assignment).filter(
        Assignment.incident_id == incident_id,
        Assignment.status == "COMPLETED"
    ).first()

    missing_items = []
    if not evidences:
        missing_items.append("Resolution completion photograph evidence is missing")
    if not assignment or not assignment.worker_notes:
        missing_items.append("Worker completion notes are missing")

    verified = len(missing_items) == 0

    log_tool_action(
        db, agent_execution_id, incident_id,
        "verify_resolution",
        {"evidences_count": len(evidences), "has_completed_assignment": bool(assignment)},
        {"verified": verified, "missing_items": missing_items}
    )

    return {
        "verified": verified,
        "missing_items": missing_items,
        "evidence_count": len(evidences),
        "notes": assignment.worker_notes if assignment else ""
    }


async def request_human_approval(
    db: Session,
    incident_id: str,
    approval_type: str,
    reason: str,
    requested_by_agent: str,
    context_data: Optional[Dict[str, Any]] = None,
    agent_execution_id: Optional[str] = None
) -> str:
    """Escalate sensitive decisions (critical priority, uncertain verification) to human admin queue."""
    valid_exec_id = None
    if agent_execution_id:
        exists_exec = db.query(AgentExecution).filter(AgentExecution.id == agent_execution_id).first()
        if exists_exec:
            valid_exec_id = agent_execution_id

    approval = HumanApproval(
        id=str(uuid.uuid4()),
        incident_id=incident_id,
        agent_execution_id=valid_exec_id,
        approval_type=approval_type,
        requested_by_agent=requested_by_agent,
        reason=reason,
        context_data=json.dumps(context_data or {}),
        status="PENDING",
        created_at=utc_now()
    )
    db.add(approval)

    # Set incident to PENDING_APPROVAL
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if incident:
        incident.status = "PENDING_APPROVAL"
        incident.requires_human_approval = True

    db.commit()

    log_tool_action(
        db, agent_execution_id, incident_id,
        "request_human_approval",
        {"approval_type": approval_type, "reason": reason, "agent": requested_by_agent},
        {"approval_id": approval.id, "status": "PENDING"}
    )

    await ws_manager.broadcast("APPROVAL_REQUESTED", {
        "approval_id": approval.id,
        "incident_id": incident_id,
        "type": approval_type,
        "reason": reason
    })

    return approval.id


async def escalate_incident(
    db: Session,
    incident_id: str,
    reason: str,
    agent_execution_id: Optional[str] = None
) -> Dict[str, Any]:
    """Escalate delayed or stalled incident."""
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if incident:
        incident.status = "ESCALATED"
        incident.requires_human_approval = True
        db.add(IncidentStatusHistory(
            id=str(uuid.uuid4()),
            incident_id=incident.id,
            old_status=incident.status,
            new_status="ESCALATED",
            change_reason=reason,
            trigger_type="AGENT",
            timestamp=utc_now()
        ))
        db.commit()

    log_tool_action(
        db, agent_execution_id, incident_id,
        "escalate_incident",
        {"reason": reason},
        {"status": "ESCALATED"}
    )

    await ws_manager.broadcast("INCIDENT_ESCALATED", {
        "incident_id": incident_id,
        "reason": reason
    })

    return {"status": "ESCALATED", "reason": reason}
