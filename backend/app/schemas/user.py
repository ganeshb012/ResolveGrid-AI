from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class DepartmentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    code: str


class UserCreateAdmin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2)
    phone: Optional[str] = None
    role: str = Field("CITIZEN", pattern="^(CITIZEN|WORKER|ADMIN)$")
    preferred_language: str = "en"
    department_id: Optional[str] = None
    employee_id: Optional[str] = None
    skills: Optional[str] = None
    address: Optional[str] = None


class UserUpdateAdmin(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    preferred_language: Optional[str] = None
    is_active: Optional[bool] = None
    department_id: Optional[str] = None
    skills: Optional[str] = None


class PasswordResetRequest(BaseModel):
    new_password: str = Field(..., min_length=6)


class UserDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    phone: Optional[str] = None
    role: str
    preferred_language: str
    is_active: bool
    created_at: datetime
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    employee_id: Optional[str] = None
    skills: Optional[str] = None
    is_on_duty: Optional[bool] = None

