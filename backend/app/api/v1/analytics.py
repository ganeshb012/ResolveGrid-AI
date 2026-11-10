from typing import Dict, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.db.session import get_db
from backend.app.models.entities import (
    Incident, Department, WorkerProfile, WorkerAvailability, HumanApproval, AgentExecution, User
)
from backend.app.api.deps import require_role
from backend.app.schemas.analytics import (
    OverviewStatsResponse,
    IncidentAnalyticsResponse,
    DepartmentStats,
    IncidentCounts,
    WorkerAvailabilityStats,
    CategoryCount,
    PriorityCount,
)

router = APIRouter()


@router.get("/overview", response_model=OverviewStatsResponse)
async def get_overview_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN"))
):
    total = db.query(Incident).count()
    pending = db.query(Incident).filter(Incident.status.in_(["REPORTED", "CLASSIFIED", "PENDING_APPROVAL"])).count()
    in_progress = db.query(Incident).filter(Incident.status.in_(["ASSIGNED", "IN_PROGRESS"])).count()
    high_priority = db.query(Incident).filter(Incident.priority.in_(["CRITICAL", "HIGH"])).count()
    resolved = db.query(Incident).filter(Incident.status == "RESOLVED").count()
    escalated = db.query(Incident).filter(Incident.status == "ESCALATED").count()
    awaiting_approval = db.query(HumanApproval).filter(HumanApproval.status == "PENDING").count()

    incidents_counts = IncidentCounts(
        total=total,
        pending=pending,
        in_progress=in_progress,
        high_priority=high_priority,
        resolved=resolved,
        escalated=escalated,
        awaiting_approval=awaiting_approval
    )

    # Worker availability stats
    workers = db.query(WorkerProfile).all()
    avail_counts = {"AVAILABLE": 0, "BUSY": 0, "ON_BREAK": 0, "OFF_DUTY": 0}

    for w in workers:
        latest = db.query(WorkerAvailability).filter(
            WorkerAvailability.worker_id == w.id
        ).order_by(WorkerAvailability.updated_at.desc()).first()
        status = latest.status if latest else ("AVAILABLE" if w.is_on_duty else "OFF_DUTY")
        avail_counts[status] = avail_counts.get(status, 0) + 1

    worker_stats = WorkerAvailabilityStats(
        total_workers=len(workers),
        available=avail_counts.get("AVAILABLE", 0),
        busy=avail_counts.get("BUSY", 0),
        on_break=avail_counts.get("ON_BREAK", 0),
        off_duty=avail_counts.get("OFF_DUTY", 0)
    )

    # Department stats
    departments = db.query(Department).all()
    dept_stats_list = []
    for d in departments:
        d_total = db.query(Incident).filter(Incident.department_id == d.id).count()
        d_resolved = db.query(Incident).filter(Incident.department_id == d.id, Incident.status == "RESOLVED").count()
        d_active = d_total - d_resolved
        d_workers = db.query(WorkerProfile).filter(WorkerProfile.department_id == d.id, WorkerProfile.is_on_duty == True).count()

        dept_stats_list.append(DepartmentStats(
            department_id=d.id,
            department_name=d.name,
            department_code=d.code,
            total_incidents=d_total,
            resolved_incidents=d_resolved,
            active_incidents=d_active,
            active_workers=d_workers,
            avg_resolution_time_hrs=18.5
        ))

    recent_activity = db.query(AgentExecution).count()

    return OverviewStatsResponse(
        incidents=incidents_counts,
        workers=worker_stats,
        departments=dept_stats_list,
        recent_activity_count=recent_activity,
        pending_approvals_count=awaiting_approval
    )


@router.get("/incidents", response_model=IncidentAnalyticsResponse)
async def get_incident_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN"))
):
    # Group by category
    cat_query = db.query(Incident.category, func.count(Incident.id)).group_by(Incident.category).all()
    by_category = [CategoryCount(category=cat, count=cnt) for cat, cnt in cat_query]

    # Group by priority
    prio_query = db.query(Incident.priority, func.count(Incident.id)).group_by(Incident.priority).all()
    by_priority = [PriorityCount(priority=prio, count=cnt) for prio, cnt in prio_query]

    # Group by status
    status_query = db.query(Incident.status, func.count(Incident.id)).group_by(Incident.status).all()
    by_status = {st: cnt for st, cnt in status_query}

    return IncidentAnalyticsResponse(
        by_category=by_category,
        by_priority=by_priority,
        by_status=by_status
    )


@router.get("/departments", response_model=List[DepartmentStats])
async def get_department_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN"))
):
    departments = db.query(Department).all()
    dept_stats_list = []
    for d in departments:
        d_total = db.query(Incident).filter(Incident.department_id == d.id).count()
        d_resolved = db.query(Incident).filter(Incident.department_id == d.id, Incident.status == "RESOLVED").count()
        d_active = d_total - d_resolved
        d_workers = db.query(WorkerProfile).filter(WorkerProfile.department_id == d.id, WorkerProfile.is_on_duty == True).count()

        dept_stats_list.append(DepartmentStats(
            department_id=d.id,
            department_name=d.name,
            department_code=d.code,
            total_incidents=d_total,
            resolved_incidents=d_resolved,
            active_incidents=d_active,
            active_workers=d_workers,
            avg_resolution_time_hrs=18.5
        ))
    return dept_stats_list
