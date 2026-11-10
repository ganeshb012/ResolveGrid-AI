import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.security import get_password_hash, verify_password, create_access_token
from backend.app.db.session import get_db
from backend.app.models.entities import User, CitizenProfile, WorkerProfile, WorkerAvailability, Department
from backend.app.schemas.auth import UserLogin, UserRegister, UserResponse, Token
from backend.app.api.deps import get_current_user

router = APIRouter()


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserRegister, db: Session = Depends(get_db)):
    # Public self-registration is strictly restricted to CITIZEN accounts
    if user_in.role and user_in.role.upper() != "CITIZEN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Public registration is available exclusively to new citizen accounts. Administrative and Field Crew accounts must be provisioned by an administrator."
        )

    if len(user_in.password.strip()) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters in length."
        )

    # Check if user already exists
    normalized_email = user_in.email.lower().strip()
    existing = db.query(User).filter(User.email == normalized_email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists."
        )

    user = User(
        id=str(uuid.uuid4()),
        email=normalized_email,
        password_hash=get_password_hash(user_in.password),
        full_name=user_in.full_name.strip(),
        phone=user_in.phone.strip() if user_in.phone else None,
        role="CITIZEN",  # Strictly enforced CITIZEN role on backend
        preferred_language=user_in.preferred_language or "en",
        is_active=True
    )
    db.add(user)
    db.flush()

    citizen = CitizenProfile(
        id=str(uuid.uuid4()),
        user_id=user.id,
        notification_preferences="ALL"
    )
    db.add(citizen)
    db.commit()
    db.refresh(user)

    token = create_access_token(
        subject=user.id,
        role=user.role,
        email=user.email
    )

    return Token(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        role=user.role,
        full_name=user.full_name,
        preferred_language=user.preferred_language
    )


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact an administrator."
        )

    token = create_access_token(
        subject=user.id,
        role=user.role,
        email=user.email
    )

    return Token(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        role=user.role,
        full_name=user.full_name,
        preferred_language=user.preferred_language
    )


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user
