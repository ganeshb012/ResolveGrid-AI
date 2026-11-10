import asyncio
import json
import logging
import time
import uuid
from typing import Any, Dict, Literal
from langgraph.graph import StateGraph, END

from backend.app.db.session import SessionLocal
from backend.app.models.entities import (
    AgentExecution, Incident, Assignment, utc_now
)
from backend.app.agents.state import AgentState
from backend.app.agents.tools import (
    classify_incident,
    find_similar_incidents,
    calculate_priority,
    get_available_workers,
    assign_worker,
    notify_worker,
    notify_citizen,
    verify_resolution,
    request_human_approval,
    update_incident_status,
)
from backend.app.websockets.manager import ws_manager

logger = logging.getLogger("resolvegrid.agents.workflow")


def record_agent_execution(
    db,
    incident_id: str,
    workflow_run_id: str,
    agent_name: str,
    input_payload: Dict[str, Any],
    output_payload: Dict[str, Any],
    reasoning_summary: str,
    status: str = "COMPLETED",
    error_message: str = None,
    latency_ms: int = 0
) -> str:
    """Record execution details into database audit table for AI Activity Center."""
    execution = AgentExecution(
        id=str(uuid.uuid4()),
        incident_id=incident_id,
        workflow_run_id=workflow_run_id,
        agent_name=agent_name,
        status=status,
        input_payload=json.dumps(input_payload),
        output_payload=json.dumps(output_payload),
        reasoning_summary=reasoning_summary,
        error_message=error_message,
        retry_count=0,
        latency_ms=latency_ms,
        started_at=utc_now(),
        completed_at=utc_now()
    )
    db.add(execution)
    db.commit()

    # Broadcast event to AI Activity Center
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(ws_manager.broadcast("AGENT_EXECUTION_COMPLETED", {
                "execution_id": execution.id,
                "agent_name": agent_name,
                "incident_id": incident_id,
                "reasoning_summary": reasoning_summary,
                "status": status,
                "latency_ms": latency_ms
            }))
    except Exception:
        pass

    return execution.id


# --- Agent Node 1: Incident Intelligence Agent ---
async def incident_intelligence_node(state: AgentState) -> Dict[str, Any]:
    """Agent 1: Understands report text, classifies category, extracts department & risks."""
    t0 = time.time()
    db = SessionLocal()
    agent_name = "INCIDENT_INTELLIGENCE"
    incident_id = state["incident_id"]
    workflow_run_id = state["workflow_run_id"]

    try:
        exec_id = str(uuid.uuid4())
        # Classify and extract structured info
        classification = await classify_incident(
            db, incident_id, f"{state['title']}: {state['description']}",
            agent_execution_id=exec_id
        )

        reasoning = (
            f"Classified infrastructure category as '{classification['category']}' under Department '{classification['department_code']}'. "
            f"Public safety risk: {classification['public_safety_risk']}."
        )
        latency = int((time.time() - t0) * 1000)
        record_agent_execution(
            db, incident_id, workflow_run_id, agent_name,
            {"title": state["title"], "description": state["description"]},
            classification, reasoning, latency_ms=latency
        )

        return {
            "category": classification["category"],
            "department_id": classification["department_id"],
            "department_code": classification["department_code"],
            "public_safety_risk": classification["public_safety_risk"],
            "urgency_reason": classification["urgency_reason"],
            "confidence_score": classification["confidence_score"],
            "status": "CLASSIFIED",
            "current_agent": agent_name,
            "completed_agents": state.get("completed_agents", []) + [agent_name],
            "logs": state.get("logs", []) + [{"agent": agent_name, "summary": reasoning}]
        }
    finally:
        db.close()


# --- Agent Node 2: Duplicate Detection Agent ---
async def duplicate_detection_node(state: AgentState) -> Dict[str, Any]:
    """Duplicate Detection: Scans within 250m radius for existing active incidents of same category."""
    t0 = time.time()
    db = SessionLocal()
    agent_name = "DUPLICATE_DETECTION"
    incident_id = state["incident_id"]
    workflow_run_id = state["workflow_run_id"]
    category = state.get("category", "OTHER")

    try:
        exec_id = str(uuid.uuid4())
        duplicate_res = await find_similar_incidents(
            db, incident_id, state["latitude"], state["longitude"], category, radius_km=0.25,
            agent_execution_id=exec_id
        )

        is_dup = bool(duplicate_res)
        dup_id = duplicate_res["duplicate_of_id"] if duplicate_res else None

        if is_dup:
            incident = db.query(Incident).filter(Incident.id == incident_id).first()
            if incident:
                incident.is_duplicate = True
                incident.duplicate_of_id = dup_id
                incident.status = "REJECTED"
                db.commit()

            reasoning = (
                f"Duplicate incident detected within 250m of active incident {duplicate_res.get('incident_number')}. "
                f"Marked as duplicate to conserve municipal resources."
            )
            latency = int((time.time() - t0) * 1000)
            record_agent_execution(
                db, incident_id, workflow_run_id, agent_name,
                {"category": category, "lat": state["latitude"], "lon": state["longitude"]},
                {"is_duplicate": True, "duplicate_of_id": dup_id},
                reasoning, latency_ms=latency
            )
            return {
                "is_duplicate": True,
                "duplicate_of_id": dup_id,
                "status": "REJECTED",
                "current_agent": agent_name,
                "completed_agents": state.get("completed_agents", []) + [agent_name],
                "logs": state.get("logs", []) + [{"agent": agent_name, "summary": reasoning}]
            }

        reasoning = f"Duplicate scan complete within 250m radius for category '{category}'. No duplicate active incidents found."
        latency = int((time.time() - t0) * 1000)
        record_agent_execution(
            db, incident_id, workflow_run_id, agent_name,
            {"category": category, "lat": state["latitude"], "lon": state["longitude"]},
            {"is_duplicate": False},
            reasoning, latency_ms=latency
        )

        return {
            "is_duplicate": False,
            "duplicate_of_id": None,
            "current_agent": agent_name,
            "completed_agents": state.get("completed_agents", []) + [agent_name],
            "logs": state.get("logs", []) + [{"agent": agent_name, "summary": reasoning}]
        }
    finally:
        db.close()


# --- Agent Node 3: Priority Assessment Agent ---
async def priority_node(state: AgentState) -> Dict[str, Any]:
    """Agent 2: Priority Assessment evaluates severity, public safety risk, and triggers human approval if required."""
    t0 = time.time()
    db = SessionLocal()
    agent_name = "PRIORITY"
    incident_id = state["incident_id"]
    workflow_run_id = state["workflow_run_id"]

    try:
        exec_id = str(uuid.uuid4())
        priority_res = await calculate_priority(
            db, incident_id, state["category"], state["public_safety_risk"], state["description"],
            agent_execution_id=exec_id
        )

        priority = priority_res["priority"]
        req_approval = priority_res["requires_human_approval"]
        approval_id = None

        if req_approval:
            approval_id = await request_human_approval(
                db, incident_id,
                "CRITICAL_HAZARD" if priority == "CRITICAL" else "HIGH_PRIORITY_ESCALATION",
                priority_res["urgency_explanation"],
                agent_name,
                context_data={"priority": priority, "category": state["category"]},
                agent_execution_id=exec_id
            )

        reasoning = (
            f"Evaluated impact urgency. Assigned priority '{priority}'. "
            f"Human oversight required: {req_approval} ({priority_res['urgency_explanation']})."
        )

        latency = int((time.time() - t0) * 1000)
        record_agent_execution(
            db, incident_id, workflow_run_id, agent_name,
            {"category": state["category"], "safety_risk": state["public_safety_risk"]},
            {**priority_res, "approval_id": approval_id},
            reasoning,
            status="AWAITING_APPROVAL" if req_approval else "COMPLETED",
            latency_ms=latency
        )

        return {
            "priority": priority,
            "requires_human_approval": req_approval,
            "approval_id": approval_id,
            "approval_reason": priority_res["urgency_explanation"] if req_approval else None,
            "status": "PENDING_APPROVAL" if req_approval else state.get("status", "CLASSIFIED"),
            "current_agent": agent_name,
            "completed_agents": state.get("completed_agents", []) + [agent_name],
            "logs": state.get("logs", []) + [{"agent": agent_name, "summary": reasoning}]
        }
    finally:
        db.close()


# --- Agent Node 4: Resource Allocation Agent ---
async def resource_allocation_node(state: AgentState) -> Dict[str, Any]:
    """Agent 3: Resource Allocation matches department, checks workload, and selects nearest worker."""
    t0 = time.time()
    db = SessionLocal()
    agent_name = "RESOURCE_ALLOCATION"
    incident_id = state["incident_id"]
    workflow_run_id = state["workflow_run_id"]

    try:
        exec_id = str(uuid.uuid4())
        # Find closest available on-duty worker
        workers = await get_available_workers(
            db, state.get("department_id"), state["latitude"], state["longitude"], max_distance_km=30.0,
            agent_execution_id=exec_id
        )

        if not workers:
            reasoning = "No available on-duty municipal workers found within 30km radius. Requesting human admin dispatch queue."
            approval_id = await request_human_approval(
                db, incident_id, "UNUSUAL_RESOURCE_ALLOCATION",
                "No worker automatically available within jurisdiction",
                agent_name, agent_execution_id=exec_id
            )
            latency = int((time.time() - t0) * 1000)
            record_agent_execution(
                db, incident_id, workflow_run_id, agent_name,
                {"dept_id": state.get("department_id")},
                {"allocated": False, "approval_id": approval_id},
                reasoning, status="AWAITING_APPROVAL", latency_ms=latency
            )
            return {
                "requires_human_approval": True,
                "approval_id": approval_id,
                "status": "PENDING_APPROVAL",
                "current_agent": agent_name,
                "completed_agents": state.get("completed_agents", []) + [agent_name],
                "logs": state.get("logs", []) + [{"agent": agent_name, "summary": reasoning}]
            }

        best = workers[0]
        # Assign best worker
        assign_res = await assign_worker(
            db, incident_id, best["worker_id"], best["distance_km"],
            assigned_by_type="AGENT", agent_execution_id=exec_id
        )

        reasoning = (
            f"Assigned closest qualified field personnel: {best['full_name']} "
            f"({best['distance_km']:.1f} km away, {best['active_tasks']} active tasks)."
        )
        latency = int((time.time() - t0) * 1000)
        record_agent_execution(
            db, incident_id, workflow_run_id, agent_name,
            {"candidates_evaluated": len(workers)},
            {"assigned_worker_id": best["worker_id"], "assignment_id": assign_res["assignment_id"]},
            reasoning, latency_ms=latency
        )

        return {
            "assigned_worker_id": best["worker_id"],
            "assigned_worker_name": best["full_name"],
            "worker_distance_km": best["distance_km"],
            "status": "ASSIGNED",
            "current_agent": agent_name,
            "completed_agents": state.get("completed_agents", []) + [agent_name],
            "logs": state.get("logs", []) + [{"agent": agent_name, "summary": reasoning}]
        }
    finally:
        db.close()


# --- Agent Node 5: Coordination Agent ---
async def coordination_node(state: AgentState) -> Dict[str, Any]:
    """Agent 4: Multi-Channel Coordination dispatches instructions to worker and alerts citizen."""
    t0 = time.time()
    db = SessionLocal()
    agent_name = "COORDINATION"
    incident_id = state["incident_id"]
    workflow_run_id = state["workflow_run_id"]

    try:
        exec_id = str(uuid.uuid4())
        worker_id = state.get("assigned_worker_id")
        citizen_id = state.get("reported_by_id")

        worker_audio = None
        citizen_audio = None

        if worker_id:
            msg = (
                f"Urgent task assigned: {state['category']} at {state['address']}. "
                f"Priority: {state['priority']}. Please review incident details and acknowledge."
            )
            w_res = await notify_worker(
                db, worker_id, incident_id, "assign-initial", msg, language="en",
                agent_execution_id=exec_id
            )
            worker_audio = w_res.get("audio_url")

        if citizen_id:
            c_msg = (
                f"Your complaint regarding {state['title']} has been acknowledged and assigned to municipal field crew {state.get('assigned_worker_name', '')}. "
                f"Status: In Progress."
            )
            c_res = await notify_citizen(
                db, incident_id, citizen_id, "Incident Assigned", c_msg, language="en",
                agent_execution_id=exec_id
            )
            citizen_audio = c_res.get("audio_url")

        reasoning = (
            f"Dispatched task notifications to assigned worker "
            f"{state.get('assigned_worker_name', '')} and reporting citizen."
        )
        latency = int((time.time() - t0) * 1000)
        record_agent_execution(
            db, incident_id, workflow_run_id, agent_name,
            {"worker_id": worker_id, "citizen_id": citizen_id},
            {"worker_audio": worker_audio, "citizen_audio": citizen_audio},
            reasoning, latency_ms=latency
        )

        return {
            "worker_notified": True,
            "citizen_notified": True,
            "worker_audio_url": worker_audio,
            "citizen_audio_url": citizen_audio,
            "current_agent": agent_name,
            "completed_agents": state.get("completed_agents", []) + [agent_name],
            "logs": state.get("logs", []) + [{"agent": agent_name, "summary": reasoning}]
        }
    except Exception as e:
        logger.exception("Error in coordination_node: %s", str(e))
        raise
    finally:
        db.close()


# --- Agent Node 6: Verification Agent ---
async def verification_node(state: AgentState) -> Dict[str, Any]:
    """Agent 5: Evidence & Resolution Verification validates photographic proof and notes before closure."""
    t0 = time.time()
    db = SessionLocal()
    agent_name = "VERIFICATION"
    incident_id = state["incident_id"]
    workflow_run_id = state["workflow_run_id"]

    try:
        exec_id = str(uuid.uuid4())
        res = await verify_resolution(db, incident_id, agent_execution_id=exec_id)

        verified = res["verified"]
        incident_rec = db.query(Incident).filter(Incident.id == incident_id).first()
        citizen_id = state.get("reported_by_id") or (incident_rec.reported_by_id if incident_rec else None)

        if verified:
            await update_incident_status(
                db, incident_id, "RESOLVED",
                "Automated verification passed: photographic proof and work completion notes validated.",
                trigger_type="AGENT", agent_execution_id=exec_id
            )
            # Notify citizen of resolution
            if citizen_id:
                inc_title = state.get("title") or (incident_rec.title if incident_rec else "complaint")
                await notify_citizen(
                    db, incident_id, citizen_id,
                    "Incident Resolved",
                    f"Your complaint regarding '{inc_title}' has been successfully resolved and verified.",
                    agent_execution_id=exec_id
                )
            reasoning = "Verification Agent inspected completion evidence: Photographic proof validated, resolution criteria satisfied. Marked incident as RESOLVED."
            status_val = "RESOLVED"
            await ws_manager.broadcast("INCIDENT_RESOLVED", {
                "incident_id": incident_id,
                "verified": True,
                "status": "RESOLVED"
            })
        else:
            missing_str = ", ".join(res["missing_items"])
            reasoning = f"Verification incomplete: {missing_str}. Requesting human approval queue."
            await request_human_approval(
                db, incident_id, "UNCERTAIN_VERIFICATION",
                f"Missing completion proof: {missing_str}",
                agent_name, agent_execution_id=exec_id
            )
            status_val = "RESOLVED_PENDING_VERIFICATION"
            if incident_rec and incident_rec.status != "RESOLVED_PENDING_VERIFICATION":
                incident_rec.status = "RESOLVED_PENDING_VERIFICATION"
                db.commit()
            await ws_manager.broadcast("VERIFICATION_FAILED", {
                "incident_id": incident_id,
                "missing_items": res["missing_items"],
                "status": "RESOLVED_PENDING_VERIFICATION"
            })

        latency = int((time.time() - t0) * 1000)
        record_agent_execution(
            db, incident_id, workflow_run_id, agent_name,
            {"verified": verified, "evidence_count": res.get("evidence_count")},
            res, reasoning,
            status="COMPLETED" if verified else "AWAITING_APPROVAL",
            latency_ms=latency
        )

        return {
            "verification_passed": verified,
            "resolution_approved": verified,
            "status": status_val,
            "current_agent": agent_name,
            "completed_agents": state.get("completed_agents", []) + [agent_name],
            "logs": state.get("logs", []) + [{"agent": agent_name, "summary": reasoning}]
        }
    finally:
        db.close()


# --- Conditional Edge Functions ---
def check_duplicate_condition(state: AgentState) -> Literal["END", "priority_node"]:
    if state.get("is_duplicate"):
        return "END"
    return "priority_node"


def check_priority_approval_condition(state: AgentState) -> Literal["resource_allocation_node", "END"]:
    # If human approval is required, stop here and wait for admin review
    if state.get("requires_human_approval"):
        return "END"
    return "resource_allocation_node"


def check_resource_condition(state: AgentState) -> Literal["coordination_node", "END"]:
    if state.get("assigned_worker_id"):
        return "coordination_node"
    return "END"


# --- Assemble Main Coordinated LangGraph Workflow ---
def create_resolvegrid_graph():
    graph = StateGraph(AgentState)

    graph.add_node("incident_intelligence_node", incident_intelligence_node)
    graph.add_node("duplicate_detection_node", duplicate_detection_node)
    graph.add_node("priority_node", priority_node)
    graph.add_node("resource_allocation_node", resource_allocation_node)
    graph.add_node("coordination_node", coordination_node)
    graph.add_node("verification_node", verification_node)

    graph.set_entry_point("incident_intelligence_node")
    graph.add_edge("incident_intelligence_node", "duplicate_detection_node")

    graph.add_conditional_edges(
        "duplicate_detection_node",
        check_duplicate_condition,
        {
            "END": END,
            "priority_node": "priority_node"
        }
    )

    graph.add_conditional_edges(
        "priority_node",
        check_priority_approval_condition,
        {
            "resource_allocation_node": "resource_allocation_node",
            "END": END
        }
    )

    graph.add_conditional_edges(
        "resource_allocation_node",
        check_resource_condition,
        {
            "coordination_node": "coordination_node",
            "END": END
        }
    )

    graph.add_edge("coordination_node", END)

    return graph.compile()


resolvegrid_workflow = create_resolvegrid_graph()


# --- Subgraph for Resuming Workflow Post-Approval ---
def create_post_approval_graph():
    graph = StateGraph(AgentState)

    graph.add_node("resource_allocation_node", resource_allocation_node)
    graph.add_node("coordination_node", coordination_node)

    graph.set_entry_point("resource_allocation_node")

    graph.add_conditional_edges(
        "resource_allocation_node",
        check_resource_condition,
        {
            "coordination_node": "coordination_node",
            "END": END
        }
    )

    graph.add_edge("coordination_node", END)

    return graph.compile()


resolvegrid_post_approval_workflow = create_post_approval_graph()


async def resume_workflow_from_resource_allocation(incident_id: str) -> Dict[str, Any]:
    """Resume multi-agent workflow from Resource Allocation after Admin grants human approval."""
    db = SessionLocal()
    try:
        incident = db.query(Incident).filter(Incident.id == incident_id).first()
        if not incident:
            logger.error("Cannot resume workflow: incident %s not found", incident_id)
            return {}

        resume_state: AgentState = {
            "incident_id": incident.id,
            "workflow_run_id": f"resume_{uuid.uuid4().hex[:8]}",
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
            "department_id": incident.department_id,
            "department_code": incident.department.code if incident.department else None,
            "assigned_worker_id": None,
            "assigned_worker_name": None,
            "worker_distance_km": None,
            "confidence_score": incident.confidence_score or 1.0,
            "is_duplicate": False,
            "duplicate_of_id": None,
            "public_safety_risk": incident.public_safety_risk,
            "urgency_reason": incident.urgency_reason,
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
            "current_agent": "RESOURCE_ALLOCATION",
            "completed_agents": ["INCIDENT_INTELLIGENCE", "DUPLICATE_DETECTION", "PRIORITY"],
            "actions_taken": [],
            "logs": [],
            "errors": []
        }
    finally:
        db.close()

    logger.info("Resuming multi-agent workflow for incident %s from Resource Allocation", incident_id)
    return await resolvegrid_post_approval_workflow.ainvoke(resume_state)


# --- Subgraph for Verification Agent Lifecycle ---
def create_verification_graph():
    graph = StateGraph(AgentState)
    graph.add_node("verification_node", verification_node)
    graph.set_entry_point("verification_node")
    graph.add_edge("verification_node", END)
    return graph.compile()


resolvegrid_verification_workflow = create_verification_graph()


async def execute_verification_workflow(incident_id: str) -> Dict[str, Any]:
    """Execute Verification Agent workflow after worker task completion."""
    db = SessionLocal()
    try:
        incident = db.query(Incident).filter(Incident.id == incident_id).first()
        if not incident:
            logger.error("Cannot run verification: incident %s not found", incident_id)
            return {"error": "Incident not found", "verified": False}

        # Prevent duplicate verification if already resolved
        if incident.status == "RESOLVED":
            logger.info("Incident %s already resolved; skipping duplicate verification", incident_id)
            return {"verified": True, "already_resolved": True, "status": "RESOLVED"}

        assignment = db.query(Assignment).filter(
            Assignment.incident_id == incident_id,
            Assignment.status == "COMPLETED"
        ).order_by(Assignment.completed_at.desc()).first()

        state: AgentState = {
            "incident_id": incident.id,
            "workflow_run_id": f"verify_{uuid.uuid4().hex[:8]}",
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
            "department_id": incident.department_id,
            "department_code": incident.department.code if incident.department else None,
            "assigned_worker_id": assignment.worker_id if assignment else None,
            "assigned_worker_name": assignment.worker.user.full_name if (assignment and assignment.worker and assignment.worker.user) else None,
            "worker_distance_km": assignment.worker_distance_km if assignment else None,
            "confidence_score": incident.confidence_score or 1.0,
            "is_duplicate": False,
            "duplicate_of_id": None,
            "public_safety_risk": incident.public_safety_risk,
            "urgency_reason": incident.urgency_reason,
            "requires_human_approval": False,
            "approval_reason": None,
            "approval_id": None,
            "escalation_reason": None,
            "worker_notified": True,
            "citizen_notified": False,
            "worker_audio_url": None,
            "citizen_audio_url": None,
            "verification_passed": False,
            "verification_notes": None,
            "resolution_approved": False,
            "current_agent": "VERIFICATION",
            "completed_agents": [],
            "actions_taken": [],
            "logs": [],
            "errors": []
        }
    finally:
        db.close()

    logger.info("Executing Verification Agent workflow for incident %s", incident_id)
    return await resolvegrid_verification_workflow.ainvoke(state)
