import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Float, Integer, Boolean, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from backend.app.db.session import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    role = Column(String(50), nullable=False, default="CITIZEN", index=True)  # CITIZEN, ADMIN, WORKER
    preferred_language = Column(String(10), default="en")  # en, mr, hi
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    citizen_profile = relationship("CitizenProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    worker_profile = relationship("WorkerProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="recipient", cascade="all, delete-orphan")


class Department(Base):
    __tablename__ = "departments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), unique=True, nullable=False)
    code = Column(String(50), unique=True, nullable=False, index=True)  # WATER, ROADS, ELECTRICAL, SANITATION, DRAINAGE, GENERAL
    description = Column(Text, nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    workers = relationship("WorkerProfile", back_populates="department")
    incidents = relationship("Incident", back_populates="department")


class CitizenProfile(Base):
    __tablename__ = "citizen_profiles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    address = Column(Text, nullable=True)
    alternate_phone = Column(String(50), nullable=True)
    notification_preferences = Column(Text, default="ALL")  # JSON or comma string
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    user = relationship("User", back_populates="citizen_profile")


class WorkerProfile(Base):
    __tablename__ = "worker_profiles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    department_id = Column(String(36), ForeignKey("departments.id"), nullable=False, index=True)
    employee_id = Column(String(50), unique=True, nullable=False, index=True)
    skills = Column(Text, default="General Maintenance")  # Comma-separated or JSON string
    current_latitude = Column(Float, nullable=True)
    current_longitude = Column(Float, nullable=True)
    last_location_update = Column(DateTime(timezone=True), nullable=True)
    is_on_duty = Column(Boolean, default=True, index=True)
    current_active_tasks = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    user = relationship("User", back_populates="worker_profile")
    department = relationship("Department", back_populates="workers")
    availabilities = relationship("WorkerAvailability", back_populates="worker", cascade="all, delete-orphan")
    assignments = relationship("Assignment", back_populates="worker")


class WorkerAvailability(Base):
    __tablename__ = "worker_availabilities"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    worker_id = Column(String(36), ForeignKey("worker_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="AVAILABLE")  # AVAILABLE, BUSY, ON_BREAK, OFF_DUTY
    notes = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    worker = relationship("WorkerProfile", back_populates="availabilities")


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    incident_number = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(100), nullable=False, default="OTHER", index=True)
    # WATER_LEAKAGE, ROAD_POTHOLE, STREETLIGHT, GARBAGE_OVERFLOW, OPEN_MANHOLE, DRAINAGE, OTHER

    priority = Column(String(50), nullable=False, default="MEDIUM", index=True)  # CRITICAL, HIGH, MEDIUM, LOW
    status = Column(String(50), nullable=False, default="REPORTED", index=True)
    # REPORTED, CLASSIFIED, PENDING_APPROVAL, ASSIGNED, IN_PROGRESS, RESOLVED_PENDING_VERIFICATION, RESOLVED, REJECTED, ESCALATED

    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    address = Column(Text, nullable=False)
    landmark = Column(String(255), nullable=True)

    reported_by_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    department_id = Column(String(36), ForeignKey("departments.id"), nullable=True, index=True)
    duplicate_of_id = Column(String(36), ForeignKey("incidents.id"), nullable=True, index=True)

    confidence_score = Column(Float, default=1.0)
    public_safety_risk = Column(Boolean, default=False)
    urgency_reason = Column(Text, nullable=True)
    estimated_resolution_time_hrs = Column(Float, default=24.0)
    is_duplicate = Column(Boolean, default=False)
    requires_human_approval = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    reporter = relationship("User", foreign_keys=[reported_by_id])
    department = relationship("Department", back_populates="incidents")
    duplicate_parent = relationship("Incident", remote_side=[id], backref="duplicates")
    reports = relationship("IncidentReport", back_populates="incident", cascade="all, delete-orphan")
    assignments = relationship("Assignment", back_populates="incident", cascade="all, delete-orphan")
    evidences = relationship("IncidentEvidence", back_populates="incident", cascade="all, delete-orphan")
    agent_executions = relationship("AgentExecution", back_populates="incident", cascade="all, delete-orphan")
    status_history = relationship("IncidentStatusHistory", back_populates="incident", cascade="all, delete-orphan")
    human_approvals = relationship("HumanApproval", back_populates="incident", cascade="all, delete-orphan")


class IncidentReport(Base):
    __tablename__ = "incident_reports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    incident_id = Column(String(36), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    citizen_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    source = Column(String(50), default="TEXT")  # TEXT, VOICE, MOBILE_PORTAL
    original_text = Column(Text, nullable=False)
    raw_audio_path = Column(String(500), nullable=True)
    language_detected = Column(String(20), default="en")
    transcription_confidence = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    incident = relationship("Incident", back_populates="reports")
    citizen = relationship("User", foreign_keys=[citizen_id])


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    incident_id = Column(String(36), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    worker_id = Column(String(36), ForeignKey("worker_profiles.id"), nullable=False, index=True)
    assigned_by_type = Column(String(50), default="AGENT")  # AGENT, ADMIN
    status = Column(String(50), default="OFFERED", index=True)
    # OFFERED, ACCEPTED, REJECTED, IN_PROGRESS, COMPLETED, CANCELLED

    offered_at = Column(DateTime(timezone=True), default=utc_now)
    responded_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    worker_distance_km = Column(Float, nullable=True)
    worker_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    incident = relationship("Incident", back_populates="assignments")
    worker = relationship("WorkerProfile", back_populates="assignments")
    evidences = relationship("IncidentEvidence", back_populates="assignment")


class IncidentEvidence(Base):
    __tablename__ = "incident_evidences"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    incident_id = Column(String(36), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    assignment_id = Column(String(36), ForeignKey("assignments.id"), nullable=True, index=True)
    uploaded_by_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    evidence_type = Column(String(50), default="PHOTO_AFTER")  # PHOTO_BEFORE, PHOTO_AFTER, AUDIO_NOTE, DOCUMENT
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    verification_status = Column(String(50), default="PENDING")  # PENDING, ACCEPTED, REJECTED
    verification_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    incident = relationship("Incident", back_populates="evidences")
    assignment = relationship("Assignment", back_populates="evidences")
    uploader = relationship("User", foreign_keys=[uploaded_by_id])


class AgentExecution(Base):
    __tablename__ = "agent_executions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    incident_id = Column(String(36), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_run_id = Column(String(100), nullable=False, index=True)
    agent_name = Column(String(100), nullable=False, index=True)
    # INCIDENT_INTELLIGENCE, PRIORITY, RESOURCE_ALLOCATION, COORDINATION, VERIFICATION

    status = Column(String(50), default="COMPLETED", index=True)  # RUNNING, COMPLETED, FAILED, ESCALATED, AWAITING_APPROVAL
    input_payload = Column(Text, nullable=True)  # JSON formatted
    output_payload = Column(Text, nullable=True)  # JSON formatted
    reasoning_summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True), default=utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    incident = relationship("Incident", back_populates="agent_executions")
    actions = relationship("AgentAction", back_populates="execution", cascade="all, delete-orphan")


class AgentAction(Base):
    __tablename__ = "agent_actions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    agent_execution_id = Column(String(36), ForeignKey("agent_executions.id", ondelete="SET NULL"), nullable=True, index=True)
    incident_id = Column(String(36), ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True, index=True)
    tool_name = Column(String(100), nullable=False, index=True)
    tool_input = Column(Text, nullable=True)
    tool_output = Column(Text, nullable=True)
    status = Column(String(50), default="SUCCESS")  # SUCCESS, FAILURE
    executed_at = Column(DateTime(timezone=True), default=utc_now)

    execution = relationship("AgentExecution", back_populates="actions")


class IncidentStatusHistory(Base):
    __tablename__ = "incident_status_histories"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    incident_id = Column(String(36), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    old_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False)
    changed_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    change_reason = Column(Text, nullable=True)
    trigger_type = Column(String(50), default="AGENT")  # CITIZEN, AGENT, WORKER, ADMIN
    timestamp = Column(DateTime(timezone=True), default=utc_now, index=True)

    incident = relationship("Incident", back_populates="status_history")
    changed_by = relationship("User", foreign_keys=[changed_by_id])


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    recipient_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    incident_id = Column(String(36), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=True, index=True)
    channel = Column(String(50), default="IN_APP")  # IN_APP, VOICE_TIMBRE, SMS, PUSH
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    audio_file_path = Column(String(500), nullable=True)
    language = Column(String(10), default="en")
    status = Column(String(50), default="SENT")  # PENDING, SENT, FAILED
    sent_at = Column(DateTime(timezone=True), default=utc_now)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    recipient = relationship("User", back_populates="notifications")
    incident = relationship("Incident")


class HumanApproval(Base):
    __tablename__ = "human_approvals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    incident_id = Column(String(36), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_execution_id = Column(String(36), ForeignKey("agent_executions.id", ondelete="SET NULL"), nullable=True)
    approval_type = Column(String(100), nullable=False)
    # HIGH_PRIORITY_ESCALATION, UNUSUAL_RESOURCE_ALLOCATION, UNCERTAIN_VERIFICATION, INCIDENT_CLOSURE

    requested_by_agent = Column(String(100), nullable=False)
    reason = Column(Text, nullable=False)
    context_data = Column(Text, nullable=True)  # JSON payload
    status = Column(String(50), default="PENDING", index=True)  # PENDING, APPROVED, REJECTED
    reviewer_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    review_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)

    incident = relationship("Incident", back_populates="human_approvals")
    reviewer = relationship("User", foreign_keys=[reviewer_id])
