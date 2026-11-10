import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.entities import WorkerProfile, WorkerAvailability, Department, User, utc_now
from backend.app.schemas.worker import WorkerResponse, WorkerUpdateAvailability, WorkerLocationUpdate
from backend.app.api.deps import get_current_user, require_role
from backend.app.websockets.manager import ws_manager

router = APIRouter()


@router.get("", response_model=List[WorkerResponse])
async def list_workers(
    department_id: Optional[str] = None,
    on_duty_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "WORKER"))
):
    query = db.query(WorkerProfile)
    if department_id:
        query = query.filter(WorkerProfile.department_id == department_id)
    if on_duty_only:
        query = query.filter(WorkerProfile.is_on_duty == True)

    workers = query.all()
    results = []
    for w in workers:
        latest_avail = db.query(WorkerAvailability).filter(
            WorkerAvailability.worker_id == w.id
        ).order_by(WorkerAvailability.updated_at.desc()).first()

        results.append(WorkerResponse(
            id=w.id,
            user_id=w.user_id,
            full_name=w.user.full_name if w.user else "Worker",
            email=w.user.email if w.user else "",
            phone=w.user.phone if w.user else None,
            department_id=w.department_id,
            department_name=w.department.name if w.department else None,
            employee_id=w.employee_id,
            skills=w.skills or "",
            current_latitude=w.current_latitude,
            current_longitude=w.current_longitude,
            is_on_duty=w.is_on_duty,
            availability_status=latest_avail.status if latest_avail else "AVAILABLE",
            current_active_tasks=w.current_active_tasks,
            created_at=w.created_at
        ))

    return results


@router.get("/me", response_model=WorkerResponse)
async def get_my_worker_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("WORKER", "ADMIN"))
):
    worker = db.query(WorkerProfile).filter(WorkerProfile.user_id == current_user.id).first()
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker profile not found")

    latest_avail = db.query(WorkerAvailability).filter(
        WorkerAvailability.worker_id == worker.id
    ).order_by(WorkerAvailability.updated_at.desc()).first()

    return WorkerResponse(
        id=worker.id,
        user_id=worker.user_id,
        full_name=current_user.full_name,
        email=current_user.email,
        phone=current_user.phone,
        department_id=worker.department_id,
        department_name=worker.department.name if worker.department else None,
        employee_id=worker.employee_id,
        skills=worker.skills or "",
        current_latitude=worker.current_latitude,
        current_longitude=worker.current_longitude,
        is_on_duty=worker.is_on_duty,
        availability_status=latest_avail.status if latest_avail else "AVAILABLE",
        current_active_tasks=worker.current_active_tasks,
        created_at=worker.created_at
    )


@router.get("/{worker_id}", response_model=WorkerResponse)
async def get_worker(
    worker_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "WORKER"))
):
    worker = db.query(WorkerProfile).filter(WorkerProfile.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")

    latest_avail = db.query(WorkerAvailability).filter(
        WorkerAvailability.worker_id == worker.id
    ).order_by(WorkerAvailability.updated_at.desc()).first()

    return WorkerResponse(
        id=worker.id,
        user_id=worker.user_id,
        full_name=worker.user.full_name if worker.user else "Worker",
        email=worker.user.email if worker.user else "",
        phone=worker.user.phone if worker.user else None,
        department_id=worker.department_id,
        department_name=worker.department.name if worker.department else None,
        employee_id=worker.employee_id,
        skills=worker.skills or "",
        current_latitude=worker.current_latitude,
        current_longitude=worker.current_longitude,
        is_on_duty=worker.is_on_duty,
        availability_status=latest_avail.status if latest_avail else "AVAILABLE",
        current_active_tasks=worker.current_active_tasks,
        created_at=worker.created_at
    )


@router.patch("/{worker_id}/availability")
async def update_worker_availability(
    worker_id: str,
    avail_in: WorkerUpdateAvailability,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    worker = db.query(WorkerProfile).filter(WorkerProfile.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")

    # Only worker themselves or admin can update
    if current_user.role != "ADMIN" and worker.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    worker.is_on_duty = (avail_in.status != "OFF_DUTY")

    new_avail = WorkerAvailability(
        id=str(uuid.uuid4()),
        worker_id=worker.id,
        status=avail_in.status,
        notes=avail_in.notes,
        updated_at=utc_now()
    )
    db.add(new_avail)
    db.commit()

    await ws_manager.broadcast("WORKER_AVAILABILITY_CHANGED", {
        "worker_id": worker_id,
        "status": avail_in.status,
        "is_on_duty": worker.is_on_duty
    })

    return {"status": "SUCCESS", "worker_id": worker_id, "availability": avail_in.status}


@router.patch("/{worker_id}/location")
async def update_worker_location(
    worker_id: str,
    loc_in: WorkerLocationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    worker = db.query(WorkerProfile).filter(WorkerProfile.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")

    # Only worker themselves or admin can update location
    if current_user.role != "ADMIN" and worker.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    worker.current_latitude = loc_in.latitude
    worker.current_longitude = loc_in.longitude
    worker.last_location_update = utc_now()
    db.commit()

    await ws_manager.broadcast("WORKER_LOCATION_UPDATED", {
        "worker_id": worker_id,
        "latitude": loc_in.latitude,
        "longitude": loc_in.longitude
    })

    return {"status": "SUCCESS", "latitude": loc_in.latitude, "longitude": loc_in.longitude}
