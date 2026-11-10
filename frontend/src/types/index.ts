export type UserRole = 'CITIZEN' | 'ADMIN' | 'WORKER';

export interface User {
  id: string;
  email: string;
  full_name: string;
  phone?: string;
  role: UserRole;
  preferred_language: string;
  is_active: boolean;
  created_at: string;
}

export type IncidentCategory =
  | 'WATER_LEAKAGE'
  | 'ROAD_POTHOLE'
  | 'STREETLIGHT'
  | 'GARBAGE_OVERFLOW'
  | 'OPEN_MANHOLE'
  | 'DRAINAGE'
  | 'OTHER';

export type IncidentPriority = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

export type IncidentStatus =
  | 'REPORTED'
  | 'CLASSIFIED'
  | 'PENDING_APPROVAL'
  | 'ASSIGNED'
  | 'IN_PROGRESS'
  | 'RESOLVED_PENDING_VERIFICATION'
  | 'RESOLVED'
  | 'REJECTED'
  | 'ESCALATED';

export interface Incident {
  id: string;
  incident_number: string;
  title: string;
  description: string;
  category: IncidentCategory;
  priority: IncidentPriority;
  status: IncidentStatus;
  latitude: number;
  longitude: number;
  address: string;
  landmark?: string;
  reported_by_id?: string;
  department_id?: string;
  department_name?: string;
  confidence_score: number;
  public_safety_risk: boolean;
  urgency_reason?: string;
  is_duplicate: boolean;
  requires_human_approval: boolean;
  created_at: string;
  updated_at: string;
  resolved_at?: string;
}

export interface IncidentStatusHistory {
  id: string;
  old_status?: string;
  new_status: string;
  change_reason?: string;
  trigger_type: string;
  timestamp: string;
}

export interface IncidentEvidence {
  id: string;
  incident_id: string;
  assignment_id?: string;
  uploaded_by_id: string;
  evidence_type: string;
  file_path: string;
  file_name: string;
  file_size: number;
  mime_type: string;
  verification_status: string;
  verification_notes?: string;
  created_at: string;
}

export interface Worker {
  id: string;
  user_id: string;
  full_name: string;
  email: string;
  phone?: string;
  department_id: string;
  department_name?: string;
  employee_id: string;
  skills: string;
  current_latitude?: number;
  current_longitude?: number;
  is_on_duty: boolean;
  availability_status: 'AVAILABLE' | 'BUSY' | 'ON_BREAK' | 'OFF_DUTY';
  current_active_tasks: number;
  created_at: string;
}

export interface Assignment {
  id: string;
  incident_id: string;
  incident_number?: string;
  incident_title?: string;
  incident_description?: string;
  incident_category?: string;
  incident_priority?: string;
  incident_status?: string;
  incident_latitude?: number;
  incident_longitude?: number;
  incident_address?: string;
  worker_id: string;
  worker_name?: string;
  assigned_by_type: string;
  status: 'OFFERED' | 'ACCEPTED' | 'REJECTED' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED';
  offered_at: string;
  responded_at?: string;
  rejection_reason?: string;
  started_at?: string;
  completed_at?: string;
  worker_distance_km?: number;
  worker_notes?: string;
}

export interface AgentAction {
  id: string;
  tool_name: string;
  tool_input?: string;
  tool_output?: string;
  status: string;
  executed_at: string;
}

export interface AgentExecution {
  id: string;
  incident_id: string;
  workflow_run_id: string;
  agent_name: string;
  status: string;
  input_payload?: string;
  output_payload?: string;
  reasoning_summary?: string;
  error_message?: string;
  retry_count: number;
  latency_ms: number;
  started_at: string;
  completed_at?: string;
  actions: AgentAction[];
}

export interface HumanApproval {
  id: string;
  incident_id: string;
  incident_number?: string;
  incident_title?: string;
  incident_priority?: string;
  agent_execution_id?: string;
  approval_type: string;
  requested_by_agent: string;
  reason: string;
  context_data?: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  reviewer_id?: string;
  reviewer_name?: string;
  review_notes?: string;
  reviewed_at?: string;
  created_at: string;
}

export interface DepartmentStats {
  department_id: string;
  department_name: string;
  department_code: string;
  total_incidents: number;
  resolved_incidents: number;
  active_incidents: number;
  active_workers: number;
  avg_resolution_time_hrs: number;
}

export interface OverviewStats {
  incidents: {
    total: number;
    pending: number;
    in_progress: number;
    high_priority: number;
    resolved: number;
    escalated: number;
    awaiting_approval: number;
  };
  workers: {
    total_workers: number;
    available: number;
    busy: number;
    on_break: number;
    off_duty: number;
  };
  departments: DepartmentStats[];
  recent_activity_count: number;
  pending_approvals_count: number;
}

export interface ServiceHealth {
  service_name: string;
  status: string;
  model: string;
  endpoint: string;
  is_live: boolean;
  details?: string;
}

export interface GnaniServicesStatusResponse {
  prisma_stt: ServiceHealth;
  timbre_tts: ServiceHealth;
  evon_reasoning: ServiceHealth;
  warp_s2s: ServiceHealth;
}
