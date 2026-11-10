import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.app.db.session import get_db
from backend.app.models.entities import (
    User, CitizenProfile, WorkerProfile, WorkerAvailability, Department, utc_now
)
from backend.app.core.security import get_password_hash
from backend.app.schemas.user import (
    UserCreateAdmin, UserUpdateAdmin, PasswordResetRequest, UserDetailResponse, DepartmentSummary
)
from backend.app.api.deps import require_role

router = APIRouter()


@router.get("/departments", response_model=List[DepartmentSummary])
async def list_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN"))
):
    """List all municipal departments for user assignment."""
    depts = db.query(Department).filter(Department.is_active == True).order_by(Department.name.asc()).all()
    return depts


@router.get("", response_model=List[UserDetailResponse])
async def list_users(
    role: Optional[str] = Query(None, description="Filter by role (CITIZEN, WORKER, ADMIN)"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    is_active: Optional[bool] = Query(None, description="Filter active status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN"))
):
    """Admin-only endpoint to list all registered users across the platform."""
    query = db.query(User)

    if role:
        query = query.filter(User.role == role.upper())

    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.filter(
            or_(
                User.full_name.ilike(search_fmt),
                User.email.ilike(search_fmt),
                User.phone.ilike(search_fmt)
            )
        )

    users = query.order_by(User.created_at.desc()).all()

    results = []
    for u in users:
        dept_id = None
        dept_name = None
        emp_id = None
        skills = None
        is_on_duty = None

        if u.role == "WORKER" and u.worker_profile:
            dept_id = u.worker_profile.department_id
            dept_name = u.worker_profile.department.name if u.worker_profile.department else None
            emp_id = u.worker_profile.employee_id
            skills = u.worker_profile.skills
            is_on_duty = u.worker_profile.is_on_duty

        results.append(UserDetailResponse(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            phone=u.phone,
            role=u.role,
            preferred_language=u.preferred_language,
            is_active=u.is_active,
            created_at=u.created_at,
            department_id=dept_id,
            department_name=dept_name,
            employee_id=emp_id,
            skills=skills,
            is_on_duty=is_on_duty
        ))

    return results


@router.post("", response_model=UserDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_user_by_admin(
    user_in: UserCreateAdmin,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN"))
):
    """Admin-only endpoint to provision new Field Crew, Citizen or Administrator accounts."""
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists."
        )

    user_role = user_in.role.upper()
    if user_role == "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Creating administrator accounts through user management is not permitted. Administrators cannot add or create another administrator."
        )

    if user_role not in ["CITIZEN", "WORKER"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role specified."
        )

    new_user = User(
        id=str(uuid.uuid4()),
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        phone=user_in.phone,
        role=user_role,
        preferred_language=user_in.preferred_language or "en",
        is_active=True
    )
    db.add(new_user)
    db.flush()

    dept_id = None
    dept_name = None
    emp_id = None
    skills = None
    is_on_duty = None

    if user_role == "CITIZEN":
        citizen = CitizenProfile(
            id=str(uuid.uuid4()),
            user_id=new_user.id,
            address=user_in.address,
            notification_preferences="ALL"
        )
        db.add(citizen)
    elif user_role == "WORKER":
        target_dept_id = user_in.department_id
        if not target_dept_id:
            first_dept = db.query(Department).filter(Department.is_active == True).first()
            if not first_dept:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No active department found. Create a department first."
                )
            target_dept_id = first_dept.id

        dept = db.query(Department).filter(Department.id == target_dept_id).first()
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found."
            )

        emp_code = user_in.employee_id or f"EMP-{uuid.uuid4().hex[:6].upper()}"
        existing_emp = db.query(WorkerProfile).filter(WorkerProfile.employee_id == emp_code).first()
        if existing_emp:
            emp_code = f"EMP-{uuid.uuid4().hex[:6].upper()}"

        worker = WorkerProfile(
            id=str(uuid.uuid4()),
            user_id=new_user.id,
            department_id=dept.id,
            employee_id=emp_code,
            skills=user_in.skills or "Field Operations & Repair",
            is_on_duty=True
        )
        db.add(worker)
        db.flush()

        avail = WorkerAvailability(
            id=str(uuid.uuid4()),
            worker_id=worker.id,
            status="AVAILABLE"
        )
        db.add(avail)

        dept_id = dept.id
        dept_name = dept.name
        emp_id = worker.employee_id
        skills = worker.skills
        is_on_duty = worker.is_on_duty

    db.commit()
    db.refresh(new_user)

    return UserDetailResponse(
        id=new_user.id,
        email=new_user.email,
        full_name=new_user.full_name,
        phone=new_user.phone,
        role=new_user.role,
        preferred_language=new_user.preferred_language,
        is_active=new_user.is_active,
        created_at=new_user.created_at,
        department_id=dept_id,
        department_name=dept_name,
        employee_id=emp_id,
        skills=skills,
        is_on_duty=is_on_duty
    )


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user_by_id(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN"))
):
    """Retrieve full account details for a specific user."""
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    dept_id = None
    dept_name = None
    emp_id = None
    skills = None
    is_on_duty = None

    if u.role == "WORKER" and u.worker_profile:
        dept_id = u.worker_profile.department_id
        dept_name = u.worker_profile.department.name if u.worker_profile.department else None
        emp_id = u.worker_profile.employee_id
        skills = u.worker_profile.skills
        is_on_duty = u.worker_profile.is_on_duty

    return UserDetailResponse(
        id=u.id,
        email=u.email,
        full_name=u.full_name,
        phone=u.phone,
        role=u.role,
        preferred_language=u.preferred_language,
        is_active=u.is_active,
        created_at=u.created_at,
        department_id=dept_id,
        department_name=dept_name,
        employee_id=emp_id,
        skills=skills,
        is_on_duty=is_on_duty
    )


@router.patch("/{user_id}", response_model=UserDetailResponse)
async def update_user(
    user_id: str,
    update_in: UserUpdateAdmin,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN"))
):
    """Admin updates user profile, activation status, or assigned worker department."""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Safety check: Prevent deactivating the last remaining active administrator
    if target_user.role == "ADMIN" and update_in.is_active is False:
        active_admins = db.query(User).filter(
            User.role == "ADMIN",
            User.is_active == True,
            User.id != target_user.id
        ).count()
        if active_admins == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the last remaining active administrator account."
            )

    if update_in.full_name is not None:
        target_user.full_name = update_in.full_name.strip()
    if update_in.phone is not None:
        target_user.phone = update_in.phone.strip()
    if update_in.preferred_language is not None:
        target_user.preferred_language = update_in.preferred_language
    if update_in.is_active is not None:
        target_user.is_active = update_in.is_active

    # Update worker profile attributes if applicable
    if target_user.role == "WORKER" and target_user.worker_profile:
        if update_in.department_id:
            dept = db.query(Department).filter(Department.id == update_in.department_id).first()
            if not dept:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
            target_user.worker_profile.department_id = dept.id
        if update_in.skills is not None:
            target_user.worker_profile.skills = update_in.skills

    db.commit()
    db.refresh(target_user)

    dept_id = None
    dept_name = None
    emp_id = None
    skills = None
    is_on_duty = None

    if target_user.role == "WORKER" and target_user.worker_profile:
        dept_id = target_user.worker_profile.department_id
        dept_name = target_user.worker_profile.department.name if target_user.worker_profile.department else None
        emp_id = target_user.worker_profile.employee_id
        skills = target_user.worker_profile.skills
        is_on_duty = target_user.worker_profile.is_on_duty

    return UserDetailResponse(
        id=target_user.id,
        email=target_user.email,
        full_name=target_user.full_name,
        phone=target_user.phone,
        role=target_user.role,
        preferred_language=target_user.preferred_language,
        is_active=target_user.is_active,
        created_at=target_user.created_at,
        department_id=dept_id,
        department_name=dept_name,
        employee_id=emp_id,
        skills=skills,
        is_on_duty=is_on_duty
    )


@router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    req: PasswordResetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN"))
):
    """Admin resets a user's password securely."""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    target_user.password_hash = get_password_hash(req.new_password)
    target_user.updated_at = utc_now()
    db.commit()

    return {"status": "SUCCESS", "message": f"Password reset successfully for user {target_user.email}"}


@router.delete("/{user_id}")
async def deactivate_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN"))
):
    """Deactivate user account. Prevents deleting or locking out the last admin."""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if target_user.role == "ADMIN":
        active_admins = db.query(User).filter(
            User.role == "ADMIN",
            User.is_active == True,
            User.id != target_user.id
        ).count()
        if active_admins == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the last remaining active administrator account."
            )

    target_user.is_active = False
    db.commit()

    return {"status": "SUCCESS", "message": f"User {target_user.email} has been deactivated."}

