from typing import Dict, List
from pydantic import BaseModel


class IncidentCounts(BaseModel):
    total: int
    pending: int
    in_progress: int
    high_priority: int
    resolved: int
    escalated: int
    awaiting_approval: int


class DepartmentStats(BaseModel):
    department_id: str
    department_name: str
    department_code: str
    total_incidents: int
    resolved_incidents: int
    active_incidents: int
    active_workers: int
    avg_resolution_time_hrs: float


class WorkerAvailabilityStats(BaseModel):
    total_workers: int
    available: int
    busy: int
    on_break: int
    off_duty: int


class OverviewStatsResponse(BaseModel):
    incidents: IncidentCounts
    workers: WorkerAvailabilityStats
    departments: List[DepartmentStats]
    recent_activity_count: int
    pending_approvals_count: int


class CategoryCount(BaseModel):
    category: str
    count: int


class PriorityCount(BaseModel):
    priority: str
    count: int


class IncidentAnalyticsResponse(BaseModel):
    by_category: List[CategoryCount]
    by_priority: List[PriorityCount]
    by_status: Dict[str, int]
