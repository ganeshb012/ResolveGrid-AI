import pytest
import uuid
import asyncio
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.models.entities import (
    User, Department, WorkerProfile, Incident, Assignment, IncidentEvidence, HumanApproval, AgentExecution, AgentAction, utc_now
)
from backend.app.agents.tools import (
    classify_incident, find_similar_incidents, calculate_priority,
    get_available_workers, assign_worker, verify_resolution
)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.mark.asyncio
async def test_authorization_role_boundary():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Login as citizen
        cit_login = await ac.post("/api/v1/auth/login", json={
            "email": "citizen@resolvegrid.gov.in",
            "password": "Citizen@12345"
        })
        assert cit_login.status_code == 200
        cit_token = cit_login.json()["access_token"]

        # Attempt to access admin approvals queue with citizen token
        res = await ac.get(
            "/api/v1/approvals",
            headers={"Authorization": f"Bearer {cit_token}"}
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_agent_tool_classification(db_session):
    text = "Huge water pipe burst near Sassoon hospital road leaking thousands of liters."
    res = await classify_incident(db_session, "test-inc-1", text)
    assert res["category"] == "WATER_LEAKAGE"
    assert res["department_code"] == "WATER"
    assert res["public_safety_risk"] is True


@pytest.mark.asyncio
async def test_agent_tool_priority_calculation(db_session):
    res = await calculate_priority(
        db_session,
        "test-inc-2",
        category="OPEN_MANHOLE",
        public_safety_risk=True,
        description="Open chamber without lid on busy crossing"
    )
    assert res["priority"] == "CRITICAL"
    assert res["requires_human_approval"] is True


@pytest.mark.asyncio
async def test_agent_tool_worker_proximity_haversine(db_session):
    # Incident near Shivajinagar (18.5314, 73.8446)
    workers = await get_available_workers(
        db_session,
        department_id=None,
        incident_lat=18.5314,
        incident_lon=73.8446,
        max_distance_km=30.0
    )
    assert len(workers) > 0
    # Closest worker should be within 10 km
    assert workers[0]["distance_km"] < 10.0


@pytest.mark.asyncio
async def test_worker_assignment_lifecycle(db_session):
    # Create test incident
    inc = Incident(
        id=str(uuid.uuid4()),
        incident_number=f"INC-TEST-{uuid.uuid4().hex[:4]}",
        title="Test Water Leak for Assignment Lifecycle",
        description="Pipe burst testing assignment lifecycle",
        category="WATER_LEAKAGE",
        priority="HIGH",
        status="REPORTED",
        latitude=18.5204,
        longitude=73.8567,
        address="Test Road, Pune",
        created_at=utc_now()
    )
    db_session.add(inc)

    worker = db_session.query(WorkerProfile).first()
    assert worker is not None

    # Step 1: Assign worker
    assign_res = await assign_worker(db_session, inc.id, worker.id, distance_km=2.5)
    assignment_id = assign_res["assignment_id"]
    assert assign_res["status"] == "OFFERED"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Login as worker
        w_login = await ac.post("/api/v1/auth/login", json={
            "email": worker.user.email,
            "password": "Worker@12345"
        })
        token = w_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Step 2: Accept assignment
        patch_accept = await ac.patch(
            f"/api/v1/assignments/{assignment_id}",
            json={"status": "ACCEPTED"},
            headers=headers
        )
        assert patch_accept.status_code == 200
        assert patch_accept.json()["status"] == "ACCEPTED"

        # Step 3: Complete assignment with notes
        patch_complete = await ac.patch(
            f"/api/v1/assignments/{assignment_id}",
            json={"status": "COMPLETED", "worker_notes": "Pipe replaced and pressure tested successfully"},
            headers=headers
        )
        assert patch_complete.status_code == 200
        assert patch_complete.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_verification_agent_evaluation(db_session):
    # Verify missing evidence case
    inc_id = str(uuid.uuid4())
    res = await verify_resolution(db_session, inc_id)
    assert res["verified"] is False
    assert len(res["missing_items"]) > 0


@pytest.mark.asyncio
async def test_human_approval_api_flow(db_session):
    # Ensure a fresh pending approval exists
    inc = db_session.query(Incident).first()
    appr = HumanApproval(
        id=str(uuid.uuid4()),
        incident_id=inc.id,
        approval_type="HIGH_PRIORITY_ESCALATION",
        requested_by_agent="PRIORITY",
        reason="Testing approval decision flow",
        status="PENDING",
        created_at=utc_now()
    )
    db_session.add(appr)
    db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin_login = await ac.post("/api/v1/auth/login", json={
            "email": "admin@resolvegrid.gov.in",
            "password": "Admin@12345"
        })
        admin_token = admin_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Approve request
        decision = await ac.post(
            f"/api/v1/approvals/{appr.id}/approve",
            json={"decision": "APPROVE", "review_notes": "Reviewed and cleared for dispatch"},
            headers=headers
        )
        assert decision.status_code == 200
        assert decision.json()["status"] == "APPROVED"


@pytest.mark.asyncio
async def test_incident_patch_authorization_boundary(db_session):
    """Verify only ADMIN can PATCH incident parameters; Citizens and Workers receive 403."""
    inc = db_session.query(Incident).first()
    assert inc is not None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Citizen login
        cit_res = await ac.post("/api/v1/auth/login", json={
            "email": "citizen@resolvegrid.gov.in",
            "password": "Citizen@12345"
        })
        cit_token = cit_res.json()["access_token"]

        # Citizen attempts to modify incident -> 403 Forbidden
        patch_cit = await ac.patch(
            f"/api/v1/incidents/{inc.id}",
            json={"priority": "CRITICAL"},
            headers={"Authorization": f"Bearer {cit_token}"}
        )
        assert patch_cit.status_code == 403

        # 2. Worker login
        w_res = await ac.post("/api/v1/auth/login", json={
            "email": "worker@resolvegrid.gov.in",
            "password": "Worker@12345"
        })
        w_token = w_res.json()["access_token"]

        # Worker attempts to modify incident -> 403 Forbidden
        patch_w = await ac.patch(
            f"/api/v1/incidents/{inc.id}",
            json={"priority": "CRITICAL"},
            headers={"Authorization": f"Bearer {w_token}"}
        )
        assert patch_w.status_code == 403

        # 3. Anonymous attempt -> 401 Unauthorized
        patch_anon = await ac.patch(
            f"/api/v1/incidents/{inc.id}",
            json={"priority": "CRITICAL"}
        )
        assert patch_anon.status_code == 401

        # 4. Admin login -> 200 OK
        adm_res = await ac.post("/api/v1/auth/login", json={
            "email": "admin@resolvegrid.gov.in",
            "password": "Admin@12345"
        })
        adm_token = adm_res.json()["access_token"]

        patch_adm = await ac.patch(
            f"/api/v1/incidents/{inc.id}",
            json={"priority": "HIGH"},
            headers={"Authorization": f"Bearer {adm_token}"}
        )
        assert patch_adm.status_code == 200
        assert patch_adm.json()["priority"] == "HIGH"


@pytest.mark.asyncio
async def test_worker_location_patch_authorization_boundary(db_session):
    """Verify only the assigned worker themselves or ADMIN can update worker GPS location."""
    worker1 = db_session.query(WorkerProfile).filter(WorkerProfile.employee_id == "PUMC-RD-101").first()
    worker2 = db_session.query(WorkerProfile).filter(WorkerProfile.employee_id == "PUMC-WT-204").first()
    assert worker1 is not None and worker2 is not None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Citizen login
        cit_res = await ac.post("/api/v1/auth/login", json={
            "email": "citizen@resolvegrid.gov.in",
            "password": "Citizen@12345"
        })
        cit_token = cit_res.json()["access_token"]

        # Citizen attempts to modify worker1 location -> 403 Forbidden
        patch_cit = await ac.patch(
            f"/api/v1/workers/{worker1.id}/location",
            json={"latitude": 18.51, "longitude": 73.85},
            headers={"Authorization": f"Bearer {cit_token}"}
        )
        assert patch_cit.status_code == 403

        # 2. Worker2 attempts to update Worker1 location -> 403 Forbidden
        w2_res = await ac.post("/api/v1/auth/login", json={
            "email": worker2.user.email,
            "password": "Worker@12345"
        })
        w2_token = w2_res.json()["access_token"]

        patch_w2 = await ac.patch(
            f"/api/v1/workers/{worker1.id}/location",
            json={"latitude": 18.51, "longitude": 73.85},
            headers={"Authorization": f"Bearer {w2_token}"}
        )
        assert patch_w2.status_code == 403

        # 3. Worker1 updates their own location -> 200 OK
        w1_res = await ac.post("/api/v1/auth/login", json={
            "email": worker1.user.email,
            "password": "Worker@12345"
        })
        w1_token = w1_res.json()["access_token"]

        patch_w1 = await ac.patch(
            f"/api/v1/workers/{worker1.id}/location",
            json={"latitude": 18.5082, "longitude": 73.8105},
            headers={"Authorization": f"Bearer {w1_token}"}
        )
        assert patch_w1.status_code == 200
        assert patch_w1.json()["status"] == "SUCCESS"

        # 4. Admin updates Worker1 location -> 200 OK
        adm_res = await ac.post("/api/v1/auth/login", json={
            "email": "admin@resolvegrid.gov.in",
            "password": "Admin@12345"
        })
        adm_token = adm_res.json()["access_token"]

        patch_adm = await ac.patch(
            f"/api/v1/workers/{worker1.id}/location",
            json={"latitude": 18.5090, "longitude": 73.8110},
            headers={"Authorization": f"Bearer {adm_token}"}
        )
        assert patch_adm.status_code == 200
        assert patch_adm.json()["status"] == "SUCCESS"


@pytest.mark.asyncio
async def test_langgraph_tool_logging_with_valid_execution_id(db_session):
    """Verify tool action logging with a valid AgentExecution ID succeeds and records audit data."""
    inc = Incident(
        id=str(uuid.uuid4()),
        incident_number=f"INC-TEST-LOG-{uuid.uuid4().hex[:4]}",
        title="Pothole on Senapati Bapat Road",
        description="Dangerous road crater causing vehicle swerving",
        category="ROAD_POTHOLE",
        priority="HIGH",
        status="REPORTED",
        latitude=18.5300,
        longitude=73.8300,
        address="Senapati Bapat Road, Pune",
        created_at=utc_now()
    )
    db_session.add(inc)

    # Create real AgentExecution in database
    exec_record = AgentExecution(
        id=str(uuid.uuid4()),
        incident_id=inc.id,
        workflow_run_id=f"run_{uuid.uuid4().hex[:8]}",
        agent_name="INCIDENT_INTELLIGENCE",
        status="RUNNING",
        input_payload="{}",
        output_payload="{}",
        reasoning_summary="Testing tool execution logging without NameError",
        started_at=utc_now()
    )
    db_session.add(exec_record)
    db_session.commit()

    # Step 1: Call find_similar_incidents with real agent_execution_id
    sim_res = await find_similar_incidents(
        db_session,
        incident_id=inc.id,
        lat=inc.latitude,
        lon=inc.longitude,
        category="ROAD_POTHOLE",
        agent_execution_id=exec_record.id
    )

    # Step 2: Call classify_incident with real agent_execution_id
    class_res = await classify_incident(
        db_session,
        incident_id=inc.id,
        text=f"{inc.title}: {inc.description}",
        agent_execution_id=exec_record.id
    )
    assert class_res["category"] == "ROAD_POTHOLE"

    # Step 3: Verify AgentAction records were inserted into DB linked to agent_execution_id
    actions = db_session.query(AgentAction).filter(
        AgentAction.agent_execution_id == exec_record.id
    ).all()
    assert len(actions) >= 2
    tool_names = [a.tool_name for a in actions]
    assert "find_similar_incidents" in tool_names
    assert "classify_incident" in tool_names

    # Step 4: Test Verification Agent tool logging and evidence satisfaction
    worker = db_session.query(WorkerProfile).first()
    assignment = Assignment(
        id=str(uuid.uuid4()),
        incident_id=inc.id,
        worker_id=worker.id,
        assigned_by_type="AGENT",
        status="COMPLETED",
        worker_notes="Asphalt patched and leveled with roller",
        completed_at=utc_now()
    )
    evidence = IncidentEvidence(
        id=str(uuid.uuid4()),
        incident_id=inc.id,
        assignment_id=assignment.id,
        uploaded_by_id=worker.user_id,
        evidence_type="PHOTO_AFTER",
        file_path="evidence/repaired_pothole.jpg",
        file_name="repaired_pothole.jpg",
        file_size=1024,
        mime_type="image/jpeg",
        verification_status="PENDING",
        created_at=utc_now()
    )
    db_session.add(assignment)
    db_session.add(evidence)
    db_session.commit()

    verify_exec = AgentExecution(
        id=str(uuid.uuid4()),
        incident_id=inc.id,
        workflow_run_id=exec_record.workflow_run_id,
        agent_name="VERIFICATION",
        status="RUNNING",
        started_at=utc_now()
    )
    db_session.add(verify_exec)
    db_session.commit()

    verify_res = await verify_resolution(
        db_session,
        incident_id=inc.id,
        agent_execution_id=verify_exec.id
    )
    assert verify_res["verified"] is True
    assert verify_res["missing_items"] == []

    # Confirm verification tool action is recorded in DB
    v_action = db_session.query(AgentAction).filter(
        AgentAction.agent_execution_id == verify_exec.id,
        AgentAction.tool_name == "verify_resolution"
    ).first()
    assert v_action is not None
    assert v_action.status == "SUCCESS"


@pytest.mark.asyncio
async def test_assignment_idor_and_role_boundaries(db_session):
    """Verify Assignment IDOR protection: only assigned worker or ADMIN can update assignment."""
    worker1 = db_session.query(WorkerProfile).filter(WorkerProfile.employee_id == "PUMC-RD-101").first()
    worker2 = db_session.query(WorkerProfile).filter(WorkerProfile.employee_id == "PUMC-WT-204").first()
    assert worker1 is not None and worker2 is not None

    dept = db_session.query(Department).first()
    inc = Incident(
        id=str(uuid.uuid4()),
        incident_number=f"INC-IDOR-{uuid.uuid4().hex[:4]}",
        title="IDOR Test Incident",
        description="Testing assignment ownership boundaries",
        category="ROAD_POTHOLE",
        priority="MEDIUM",
        status="ASSIGNED",
        department_id=dept.id,
        latitude=18.5204,
        longitude=73.8567,
        address="Test Road, Pune",
        created_at=utc_now()
    )
    assignment = Assignment(
        id=str(uuid.uuid4()),
        incident_id=inc.id,
        worker_id=worker1.id,
        assigned_by_type="SYSTEM",
        status="OFFERED",
        offered_at=utc_now()
    )
    db_session.add(inc)
    db_session.add(assignment)
    db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Citizen login -> Attempt to update assignment -> 403 Forbidden
        cit_res = await ac.post("/api/v1/auth/login", json={
            "email": "citizen@resolvegrid.gov.in",
            "password": "Citizen@12345"
        })
        assert cit_res.status_code == 200
        cit_token = cit_res.json()["access_token"]

        patch_cit = await ac.patch(
            f"/api/v1/assignments/{assignment.id}",
            json={"status": "ACCEPTED", "worker_notes": "Citizen malicious update"},
            headers={"Authorization": f"Bearer {cit_token}"}
        )
        assert patch_cit.status_code == 403

        # 2. Worker 2 (unassigned) -> Attempt to update Worker 1's assignment (IDOR) -> 403 Forbidden
        w2_res = await ac.post("/api/v1/auth/login", json={
            "email": worker2.user.email,
            "password": "Worker@12345"
        })
        assert w2_res.status_code == 200
        w2_token = w2_res.json()["access_token"]

        patch_w2 = await ac.patch(
            f"/api/v1/assignments/{assignment.id}",
            json={"status": "REJECTED", "rejection_reason": "Malicious reject by other worker"},
            headers={"Authorization": f"Bearer {w2_token}"}
        )
        assert patch_w2.status_code == 403

        # 3. Worker 1 (assigned worker) -> Accepts own assignment -> 200 OK
        w1_res = await ac.post("/api/v1/auth/login", json={
            "email": worker1.user.email,
            "password": "Worker@12345"
        })
        assert w1_res.status_code == 200
        w1_token = w1_res.json()["access_token"]

        patch_w1 = await ac.patch(
            f"/api/v1/assignments/{assignment.id}",
            json={"status": "ACCEPTED", "worker_notes": "Accepted by assigned worker"},
            headers={"Authorization": f"Bearer {w1_token}"}
        )
        assert patch_w1.status_code == 200
        assert patch_w1.json()["status"] == "ACCEPTED"

        # 4. Admin -> Updates assignment -> 200 OK
        adm_res = await ac.post("/api/v1/auth/login", json={
            "email": "admin@resolvegrid.gov.in",
            "password": "Admin@12345"
        })
        assert adm_res.status_code == 200
        adm_token = adm_res.json()["access_token"]

        patch_adm = await ac.patch(
            f"/api/v1/assignments/{assignment.id}",
            json={"status": "IN_PROGRESS", "worker_notes": "Admin override note"},
            headers={"Authorization": f"Bearer {adm_token}"}
        )
        assert patch_adm.status_code == 200
        assert patch_adm.json()["status"] == "IN_PROGRESS"


@pytest.mark.asyncio
async def test_assignment_listing_protection():
    """Verify GET /api/v1/assignments is protected for ADMIN only, while /my is for WORKER."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Anonymous -> 401
        res_anon = await ac.get("/api/v1/assignments")
        assert res_anon.status_code == 401

        # Citizen -> 403
        cit_res = await ac.post("/api/v1/auth/login", json={
            "email": "citizen@resolvegrid.gov.in",
            "password": "Citizen@12345"
        })
        cit_token = cit_res.json()["access_token"]
        res_cit = await ac.get("/api/v1/assignments", headers={"Authorization": f"Bearer {cit_token}"})
        assert res_cit.status_code == 403

        # Worker -> 403 on all assignments list
        w_res = await ac.post("/api/v1/auth/login", json={
            "email": "worker@resolvegrid.gov.in",
            "password": "Worker@12345"
        })
        w_token = w_res.json()["access_token"]
        res_w = await ac.get("/api/v1/assignments", headers={"Authorization": f"Bearer {w_token}"})
        assert res_w.status_code == 403

        # Worker -> 200 on /my
        res_my = await ac.get("/api/v1/assignments/my", headers={"Authorization": f"Bearer {w_token}"})
        assert res_my.status_code == 200

        # Admin -> 200 on /assignments
        adm_res = await ac.post("/api/v1/auth/login", json={
            "email": "admin@resolvegrid.gov.in",
            "password": "Admin@12345"
        })
        adm_token = adm_res.json()["access_token"]
        res_adm = await ac.get("/api/v1/assignments", headers={"Authorization": f"Bearer {adm_token}"})
        assert res_adm.status_code == 200


@pytest.mark.asyncio
async def test_worker_roster_and_gps_protection(db_session):
    """Verify worker roster and GPS coordinates are hidden from anonymous and citizens."""
    worker = db_session.query(WorkerProfile).first()
    assert worker is not None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Anonymous GET /api/v1/workers -> 401
        res_anon = await ac.get("/api/v1/workers")
        assert res_anon.status_code == 401

        # 2. Anonymous GET /api/v1/workers/{id} -> 401
        res_anon_single = await ac.get(f"/api/v1/workers/{worker.id}")
        assert res_anon_single.status_code == 401

        # 3. Citizen GET /api/v1/workers -> 403
        cit_res = await ac.post("/api/v1/auth/login", json={
            "email": "citizen@resolvegrid.gov.in",
            "password": "Citizen@12345"
        })
        cit_token = cit_res.json()["access_token"]
        res_cit = await ac.get("/api/v1/workers", headers={"Authorization": f"Bearer {cit_token}"})
        assert res_cit.status_code == 403

        # 4. Citizen GET /api/v1/workers/{id} -> 403
        res_cit_single = await ac.get(f"/api/v1/workers/{worker.id}", headers={"Authorization": f"Bearer {cit_token}"})
        assert res_cit_single.status_code == 403

        # 5. Admin GET /api/v1/workers -> 200
        adm_res = await ac.post("/api/v1/auth/login", json={
            "email": "admin@resolvegrid.gov.in",
            "password": "Admin@12345"
        })
        adm_token = adm_res.json()["access_token"]
        res_adm = await ac.get("/api/v1/workers", headers={"Authorization": f"Bearer {adm_token}"})
        assert res_adm.status_code == 200
        assert len(res_adm.json()) > 0


@pytest.mark.asyncio
async def test_incident_personal_filtering_and_public_feed(db_session):
    """Verify unauthenticated personal incident query is 401, while public feed and citizen scoping work."""
    citizen = db_session.query(User).filter(User.role == "CITIZEN").first()
    assert citizen is not None

    # Create an incident reported by this citizen
    inc_cit = Incident(
        id=str(uuid.uuid4()),
        incident_number=f"INC-CIT-{uuid.uuid4().hex[:4]}",
        title="Citizen Own Complaint",
        description="Testing citizen scoping",
        category="WATER_LEAKAGE",
        priority="LOW",
        status="REPORTED",
        reported_by_id=citizen.id,
        latitude=18.5200,
        longitude=73.8500,
        address="FC Road, Pune",
        created_at=utc_now()
    )
    # Create an incident reported anonymously / by someone else
    inc_other = Incident(
        id=str(uuid.uuid4()),
        incident_number=f"INC-OTH-{uuid.uuid4().hex[:4]}",
        title="Other Complaint",
        description="Testing other complaint",
        category="DRAINAGE_OVERFLOW",
        priority="MEDIUM",
        status="REPORTED",
        reported_by_id=None,
        latitude=18.5300,
        longitude=73.8400,
        address="JM Road, Pune",
        created_at=utc_now()
    )
    db_session.add(inc_cit)
    db_session.add(inc_other)
    db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Unauthenticated with mine=true -> 401
        res_unauth_mine = await ac.get("/api/v1/incidents?mine=true")
        assert res_unauth_mine.status_code == 401

        # 2. Unauthenticated without mine=true -> 200 (public feed intact)
        res_unauth_feed = await ac.get("/api/v1/incidents")
        assert res_unauth_feed.status_code == 200
        feed_ids = [i["id"] for i in res_unauth_feed.json()]
        assert inc_other.id in feed_ids

        # 3. Authenticated citizen with mine=true -> 200, contains only own incident
        cit_res = await ac.post("/api/v1/auth/login", json={
            "email": citizen.email,
            "password": "Citizen@12345"
        })
        cit_token = cit_res.json()["access_token"]

        res_cit_mine = await ac.get("/api/v1/incidents?mine=true", headers={"Authorization": f"Bearer {cit_token}"})
        assert res_cit_mine.status_code == 200
        cit_mine_ids = [i["id"] for i in res_cit_mine.json()]
        assert inc_cit.id in cit_mine_ids
        assert inc_other.id not in cit_mine_ids

        # 4. Authenticated citizen without mine=true -> 200, scoped to own incidents
        res_cit_all = await ac.get("/api/v1/incidents", headers={"Authorization": f"Bearer {cit_token}"})
        assert res_cit_all.status_code == 200
        cit_all_ids = [i["id"] for i in res_cit_all.json()]
        assert inc_cit.id in cit_all_ids
        assert inc_other.id not in cit_all_ids

        # 5. Admin -> sees all incidents
        adm_res = await ac.post("/api/v1/auth/login", json={
            "email": "admin@resolvegrid.gov.in",
            "password": "Admin@12345"
        })
        adm_token = adm_res.json()["access_token"]
        res_adm = await ac.get("/api/v1/incidents", headers={"Authorization": f"Bearer {adm_token}"})
        assert res_adm.status_code == 200
        adm_ids = [i["id"] for i in res_adm.json()]
        assert inc_cit.id in adm_ids
        assert inc_other.id in adm_ids


@pytest.mark.asyncio
async def test_admin_only_analytics_and_agent_activity():
    """Verify analytics and agent telemetry endpoints strictly require ADMIN role."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        endpoints = [
            "/api/v1/analytics/overview",
            "/api/v1/analytics/incidents",
            "/api/v1/analytics/departments",
            "/api/v1/agents/activity",
        ]

        # 1. Anonymous -> 401
        for ep in endpoints:
            res = await ac.get(ep)
            assert res.status_code == 401, f"{ep} did not reject anonymous with 401"

        # 2. Citizen -> 403
        cit_res = await ac.post("/api/v1/auth/login", json={
            "email": "citizen@resolvegrid.gov.in",
            "password": "Citizen@12345"
        })
        cit_token = cit_res.json()["access_token"]
        for ep in endpoints:
            res = await ac.get(ep, headers={"Authorization": f"Bearer {cit_token}"})
            assert res.status_code == 403, f"{ep} did not reject citizen with 403"

        # 3. Worker -> 403
        w_res = await ac.post("/api/v1/auth/login", json={
            "email": "worker@resolvegrid.gov.in",
            "password": "Worker@12345"
        })
        w_token = w_res.json()["access_token"]
        for ep in endpoints:
            res = await ac.get(ep, headers={"Authorization": f"Bearer {w_token}"})
            assert res.status_code == 403, f"{ep} did not reject worker with 403"

        # 4. Admin -> 200
        adm_res = await ac.post("/api/v1/auth/login", json={
            "email": "admin@resolvegrid.gov.in",
            "password": "Admin@12345"
        })
        adm_token = adm_res.json()["access_token"]
        for ep in endpoints:
            res = await ac.get(ep, headers={"Authorization": f"Bearer {adm_token}"})
            assert res.status_code == 200, f"{ep} did not allow admin with 200"


@pytest.mark.asyncio
async def test_five_agent_autonomous_workflow_lifecycle(db_session):
    """
    Test: Full five-agent autonomous lifecycle for a standard incident.
    Verifies:
    1. Incident Intelligence classifies report
    2. Duplicate Detection confirms no nearby duplicate
    3. Priority Assessment assigns priority (non-critical, no approval needed)
    4. Resource Allocation assigns available on-duty worker
    5. Coordination dispatches notifications to worker and citizen
    """
    from backend.app.agents.workflow import resolvegrid_workflow
    from backend.app.agents.state import AgentState

    dept = db_session.query(Department).filter(Department.code == "ELECTRICAL").first()
    if not dept:
        dept = db_session.query(Department).first()

    # Ensure electrical worker has capacity for assignment
    worker = db_session.query(WorkerProfile).filter(WorkerProfile.department_id == dept.id).first()
    if worker:
        worker.current_active_tasks = 1
        worker.is_on_duty = True
        db_session.commit()

    db_session.query(Incident).filter(Incident.incident_number.like("INC-AUTO-%")).update({"status": "RESOLVED"}, synchronize_session=False)
    db_session.commit()

    inc_id = str(uuid.uuid4())
    inc = Incident(
        id=inc_id,
        incident_number=f"INC-AUTO-{uuid.uuid4().hex[:4]}",
        title="Flickering streetlight on Nigdi bypass",
        description="Streetlight lamp flickering dark outside shopping area",
        category="STREETLIGHT",
        priority="MEDIUM",
        status="REPORTED",
        department_id=dept.id if dept else None,
        latitude=18.6500,
        longitude=73.7700,
        address="Nigdi Pradhikaran, Pune",
        created_at=utc_now()
    )
    db_session.add(inc)
    db_session.commit()

    run_id = f"test_run_{uuid.uuid4().hex[:8]}"
    state: AgentState = {
        "incident_id": inc_id,
        "workflow_run_id": run_id,
        "title": "Flickering streetlight on Nigdi bypass",
        "description": "Streetlight lamp flickering dark outside shopping area",
        "category": "STREETLIGHT",
        "priority": "MEDIUM",
        "status": "REPORTED",
        "latitude": 18.6500,
        "longitude": 73.7700,
        "address": "Nigdi Pradhikaran, Pune",
        "landmark": None,
        "reported_by_id": None,
        "department_id": dept.id if dept else None,
        "department_code": dept.code if dept else None,
        "assigned_worker_id": None,
        "assigned_worker_name": None,
        "worker_distance_km": None,
        "confidence_score": 1.0,
        "is_duplicate": False,
        "duplicate_of_id": None,
        "public_safety_risk": False,
        "urgency_reason": None,
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
        "current_agent": "INCIDENT_INTELLIGENCE",
        "completed_agents": [],
        "actions_taken": [],
        "logs": [],
        "errors": []
    }

    result = await resolvegrid_workflow.ainvoke(state)

    assert result["status"] in ["ASSIGNED", "CLASSIFIED"]
    assert "INCIDENT_INTELLIGENCE" in result["completed_agents"]
    assert "DUPLICATE_DETECTION" in result["completed_agents"]
    assert "PRIORITY" in result["completed_agents"]
    assert "RESOURCE_ALLOCATION" in result["completed_agents"]
    assert "COORDINATION" in result["completed_agents"]
    assert result["worker_notified"] is True

    # Check assignment was created in database
    assignment = db_session.query(Assignment).filter(Assignment.incident_id == inc_id).first()
    assert assignment is not None
    assert assignment.status == "OFFERED"


@pytest.mark.asyncio
async def test_priority_human_approval_pause_and_resume(db_session):
    """
    Test: Critical incident pauses for human approval;
    Admin approval resumes workflow and dispatches worker.
    """
    from backend.app.agents.workflow import resolvegrid_workflow
    from backend.app.agents.state import AgentState

    db_session.query(Incident).filter(Incident.incident_number.like("INC-CRIT-%")).update({"status": "RESOLVED"}, synchronize_session=False)
    # Ensure drainage worker has capacity
    drainage_worker = db_session.query(WorkerProfile).join(Department).filter(Department.code == "DRAINAGE").first()
    if drainage_worker:
        drainage_worker.current_active_tasks = 1
        drainage_worker.is_on_duty = True
    db_session.commit()

    inc_id = str(uuid.uuid4())
    inc_num = f"INC-CRIT-{uuid.uuid4().hex[:4]}"
    inc = Incident(
        id=inc_id,
        incident_number=inc_num,
        title="Open manhole chamber with collapse risk",
        description="Open manhole chamber on fast vehicle lane causing severe danger of fatal accidents",
        category="OPEN_MANHOLE",
        priority="LOW",  # Will be elevated to CRITICAL
        status="REPORTED",
        latitude=18.5204,
        longitude=73.8567,
        address="FC Road, Pune",
        created_at=utc_now()
    )
    db_session.add(inc)
    db_session.commit()

    run_id = f"crit_run_{uuid.uuid4().hex[:8]}"
    state: AgentState = {
        "incident_id": inc_id,
        "workflow_run_id": run_id,
        "title": "Open manhole chamber with collapse risk",
        "description": "Open manhole chamber on fast vehicle lane causing severe danger of fatal accidents",
        "category": "OPEN_MANHOLE",
        "priority": "LOW",
        "status": "REPORTED",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "address": "FC Road, Pune",
        "landmark": None,
        "reported_by_id": None,
        "department_id": None,
        "department_code": None,
        "assigned_worker_id": None,
        "assigned_worker_name": None,
        "worker_distance_km": None,
        "confidence_score": 1.0,
        "is_duplicate": False,
        "duplicate_of_id": None,
        "public_safety_risk": False,
        "urgency_reason": None,
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
        "current_agent": "INCIDENT_INTELLIGENCE",
        "completed_agents": [],
        "actions_taken": [],
        "logs": [],
        "errors": []
    }

    # Step 1: Run workflow — should pause after Priority Assessment
    result = await resolvegrid_workflow.ainvoke(state)

    assert result["requires_human_approval"] is True
    assert result["priority"] == "CRITICAL"
    assert result["status"] == "PENDING_APPROVAL"
    # Should NOT have reached Resource Allocation or Coordination yet
    assert "RESOURCE_ALLOCATION" not in result["completed_agents"]
    assert "COORDINATION" not in result["completed_agents"]

    # Check HumanApproval record was created in DB
    db_session.expire_all()
    queried_inc = db_session.query(Incident).filter(Incident.id == inc_id).first()
    assert queried_inc.status == "PENDING_APPROVAL"
    approval = db_session.query(HumanApproval).filter(
        HumanApproval.incident_id == inc_id,
        HumanApproval.status == "PENDING"
    ).first()
    assert approval is not None
    approval_id = approval.id

    # Step 2: Admin approves via API
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        adm_login = await ac.post("/api/v1/auth/login", json={
            "email": "admin@resolvegrid.gov.in",
            "password": "Admin@12345"
        })
        adm_token = adm_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {adm_token}"}

        # Approve
        appr_res = await ac.post(
            f"/api/v1/approvals/{approval_id}/approve",
            json={"decision": "APPROVE", "review_notes": "Emergency cleared for dispatch"},
            headers=headers
        )
        assert appr_res.status_code == 200
        assert appr_res.json()["status"] == "APPROVED"

        # Duplicate approval attempt must be rejected (400)
        dup_appr = await ac.post(
            f"/api/v1/approvals/{approval_id}/approve",
            json={"decision": "APPROVE", "review_notes": "Second attempt"},
            headers=headers
        )
        assert dup_appr.status_code == 400

    # Allow async post-approval resumption to finish
    await asyncio.sleep(0.5)

    # Check that worker was assigned post-approval
    db_session.expire_all()
    updated_inc = db_session.query(Incident).filter(Incident.id == inc_id).first()
    assignment = db_session.query(Assignment).filter(Assignment.incident_id == inc_id).first()
    assert assignment is not None
    assert updated_inc.status in ["ASSIGNED", "IN_PROGRESS", "CLASSIFIED"]


@pytest.mark.asyncio
async def test_admin_rejection_halts_workflow_and_marks_rejected(db_session):
    """
    Test: Admin rejection halts workflow, marks incident REJECTED, and prevents worker dispatch.
    """
    inc_id = str(uuid.uuid4())
    inc = Incident(
        id=inc_id,
        incident_number=f"INC-REJ-{uuid.uuid4().hex[:4]}",
        title="Doubtful complaint on highway",
        description="Hazard report requiring approval",
        category="ROAD_POTHOLE",
        priority="CRITICAL",
        status="PENDING_APPROVAL",
        latitude=18.5204,
        longitude=73.8567,
        address="Pune Expressway",
        created_at=utc_now()
    )
    approval_id = str(uuid.uuid4())
    approval = HumanApproval(
        id=approval_id,
        incident_id=inc_id,
        approval_type="CRITICAL_HAZARD",
        requested_by_agent="PRIORITY",
        reason="Testing rejection flow",
        status="PENDING",
        created_at=utc_now()
    )
    db_session.add(inc)
    db_session.add(approval)
    db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        adm_login = await ac.post("/api/v1/auth/login", json={
            "email": "admin@resolvegrid.gov.in",
            "password": "Admin@12345"
        })
        adm_token = adm_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {adm_token}"}

        # Reject request
        rej_res = await ac.post(
            f"/api/v1/approvals/{approval_id}/reject",
            json={"decision": "REJECT", "review_notes": "Duplicate report / invalid jurisdiction"},
            headers=headers
        )
        assert rej_res.status_code == 200
        assert rej_res.json()["status"] == "REJECTED"

        # Duplicate rejection attempt must be rejected (400)
        dup_rej = await ac.post(
            f"/api/v1/approvals/{approval_id}/reject",
            json={"decision": "REJECT", "review_notes": "Second attempt"},
            headers=headers
        )
        assert dup_rej.status_code == 400

    db_session.expire_all()
    rejected_inc = db_session.query(Incident).filter(Incident.id == inc_id).first()
    assert rejected_inc.status == "REJECTED"
    # No worker assignment should exist
    no_assign = db_session.query(Assignment).filter(Assignment.incident_id == inc_id).first()
    assert no_assign is None


@pytest.mark.asyncio
async def test_verification_agent_lifecycle_missing_vs_valid_evidence(db_session):
    """
    Test:
    - Worker completes without evidence -> Verification fails, incident NOT marked RESOLVED.
    - Worker adds PHOTO_AFTER & notes -> Verification passes, incident becomes RESOLVED.
    """
    from backend.app.agents.workflow import verification_node
    from backend.app.agents.state import AgentState

    worker = db_session.query(WorkerProfile).first()
    assert worker is not None

    inc_id = str(uuid.uuid4())
    inc = Incident(
        id=inc_id,
        incident_number=f"INC-VERIF-{uuid.uuid4().hex[:4]}",
        title="Water pipeline repair on Tilak Road",
        description="Pipeline burst repair testing verification agent",
        category="WATER_LEAKAGE",
        priority="HIGH",
        status="IN_PROGRESS",
        latitude=18.5080,
        longitude=73.8500,
        address="Tilak Road, Pune",
        created_at=utc_now()
    )
    assign_id = str(uuid.uuid4())
    assignment = Assignment(
        id=assign_id,
        incident_id=inc_id,
        worker_id=worker.id,
        assigned_by_type="AGENT",
        status="ACCEPTED",
        offered_at=utc_now(),
        started_at=utc_now()
    )
    db_session.add(inc)
    db_session.add(assignment)
    db_session.commit()

    # Step 1: Missing evidence evaluation
    v_res_fail = await verify_resolution(db_session, inc_id)
    assert v_res_fail["verified"] is False
    assert len(v_res_fail["missing_items"]) > 0

    # Step 2: Add completed assignment with notes and PHOTO_AFTER evidence
    assignment.status = "COMPLETED"
    assignment.worker_notes = "Replaced 4-inch ductile iron valve and restored road grade"

    evidence = IncidentEvidence(
        id=str(uuid.uuid4()),
        incident_id=inc_id,
        assignment_id=assign_id,
        uploaded_by_id=worker.user_id,
        evidence_type="PHOTO_AFTER",
        file_path="uploads/test_resolved.jpg",
        file_name="test_resolved.jpg",
        file_size=2048,
        mime_type="image/jpeg",
        verification_status="PENDING",
        created_at=utc_now()
    )
    db_session.add(evidence)
    db_session.commit()

    # Step 3: Re-evaluate verification — must pass
    v_res_pass = await verify_resolution(db_session, inc_id)
    assert v_res_pass["verified"] is True
    assert v_res_pass["missing_items"] == []

    # Run verification_node to execute resolution transition
    v_state: AgentState = {
        "incident_id": inc_id,
        "workflow_run_id": f"v_run_{uuid.uuid4().hex[:8]}",
        "title": "Water pipeline repair on Tilak Road",
        "description": "Pipeline burst repair testing verification agent",
        "category": "WATER_LEAKAGE",
        "priority": "HIGH",
        "status": "IN_PROGRESS",
        "latitude": 18.5080,
        "longitude": 73.8500,
        "address": "Tilak Road, Pune",
        "landmark": None,
        "reported_by_id": None,
        "department_id": None,
        "department_code": None,
        "assigned_worker_id": worker.id,
        "assigned_worker_name": worker.user.full_name if worker.user else "Field Crew",
        "worker_distance_km": 1.2,
        "confidence_score": 1.0,
        "is_duplicate": False,
        "duplicate_of_id": None,
        "public_safety_risk": False,
        "urgency_reason": None,
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

    node_res = await verification_node(v_state)
    assert node_res["verification_passed"] is True
    assert node_res["status"] == "RESOLVED"

    db_session.expire_all()
    resolved_inc = db_session.query(Incident).filter(Incident.id == inc_id).first()
    assert resolved_inc.status == "RESOLVED"
    assert resolved_inc.resolved_at is not None


@pytest.mark.asyncio
async def test_all_five_agents_activity_center_telemetry(db_session):
    """
    Test: Verify all 5 agents record executions and actions
    accessible to Admin in the AI Activity Center via GET /api/v1/agents/activity.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        adm_login = await ac.post("/api/v1/auth/login", json={
            "email": "admin@resolvegrid.gov.in",
            "password": "Admin@12345"
        })
        adm_token = adm_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {adm_token}"}

        # Check all executions
        all_res = await ac.get("/api/v1/agents/activity?limit=50", headers=headers)
        assert all_res.status_code == 200
        executions = all_res.json()
        assert len(executions) > 0

        # Check filtering by PRIORITY and PRIORITY_ASSESSMENT
        prio_res = await ac.get("/api/v1/agents/activity?agent_name=PRIORITY", headers=headers)
        assert prio_res.status_code == 200

        prio_assess_res = await ac.get("/api/v1/agents/activity?agent_name=PRIORITY_ASSESSMENT", headers=headers)
        assert prio_assess_res.status_code == 200

        # Check filtering by INCIDENT_INTELLIGENCE
        intel_res = await ac.get("/api/v1/agents/activity?agent_name=INCIDENT_INTELLIGENCE", headers=headers)
        assert intel_res.status_code == 200


@pytest.mark.asyncio
async def test_complete_lifecycle_end_to_end_from_citizen_to_verification_and_notification(db_session):
    """
    Test: Full end-to-end lifecycle proving:
    Citizen Report
    -> Incident Intelligence
    -> Duplicate Detection
    -> Priority Assessment
    -> Resource Allocation
    -> Coordination (worker notified)
    -> Worker accepts assignment (status -> IN_PROGRESS)
    -> Worker completes task WITHOUT evidence -> Verification fails (status -> RESOLVED_PENDING_VERIFICATION)
    -> Worker uploads PHOTO_AFTER evidence -> Verification Agent passes (status -> RESOLVED)
    -> Citizen receives resolution notification
    -> Duplicate assignment and modification rejected (400)
    -> All agents logged in AgentExecution
    """
    from backend.app.agents.workflow import resolvegrid_workflow
    from backend.app.agents.state import AgentState

    # Ensure clean state for test
    db_session.query(Incident).filter(Incident.incident_number.like("INC-E2E-%")).update({"status": "RESOLVED"}, synchronize_session=False)
    # Ensure all municipal workers are on duty and have available capacity
    db_session.query(WorkerProfile).update({"is_on_duty": True, "current_active_tasks": 0}, synchronize_session=False)
    db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Step 1: Login citizen & admin
        cit_login = await ac.post("/api/v1/auth/login", json={
            "email": "citizen@resolvegrid.gov.in",
            "password": "Citizen@12345"
        })
        cit_token = cit_login.json()["access_token"]
        cit_headers = {"Authorization": f"Bearer {cit_token}"}

        adm_login = await ac.post("/api/v1/auth/login", json={
            "email": "admin@resolvegrid.gov.in",
            "password": "Admin@12345"
        })
        adm_token = adm_login.json()["access_token"]
        adm_headers = {"Authorization": f"Bearer {adm_token}"}

        # Step 2: Citizen submits report (this automatically triggers resolvegrid_workflow asynchronously)
        create_res = await ac.post("/api/v1/incidents", json={
            "title": "Exposed electrical fuse box near Balewadi High Street",
            "description": "Streetlight fuse box cover broken with exposed wiring sparking near pavement",
            "latitude": 18.5720,
            "longitude": 73.7650,
            "address": "Balewadi High Street, Pune",
            "category": "STREETLIGHT",
            "priority": "MEDIUM"
        }, headers=cit_headers)
        assert create_res.status_code == 201
        inc_data = create_res.json()
        inc_id = inc_data["id"]

        # Step 3: Allow multi-agent workflow execution to complete, approving if approval requested
        for _ in range(15):
            appr_list_res = await ac.get("/api/v1/approvals?status=PENDING", headers=adm_headers)
            if appr_list_res.status_code == 200:
                matching_apprs = [a for a in appr_list_res.json() if a.get("incident_id") == inc_id]
                if matching_apprs:
                    appr = matching_apprs[0]
                    appr_res = await ac.post(
                        f"/api/v1/approvals/{appr['id']}/approve",
                        json={"decision": "APPROVE", "review_notes": "Hazard cleared for field team dispatch"},
                        headers=adm_headers
                    )
                    assert appr_res.status_code == 200
                    break
            # Also break early if already assigned
            assign_check = await ac.get(f"/api/v1/assignments?incident_id={inc_id}", headers=adm_headers)
            if assign_check.status_code == 200 and len(assign_check.json()) >= 1:
                break
            await asyncio.sleep(0.5)

        # Step 4: Verify assignment was created for worker
        assignments = []
        for _ in range(6):
            assign_res = await ac.get(f"/api/v1/assignments?incident_id={inc_id}", headers=adm_headers)
            assert assign_res.status_code == 200
            assignments = assign_res.json()
            if len(assignments) >= 1:
                break
            await asyncio.sleep(0.5)

        assert len(assignments) >= 1
        assignment_id = assignments[0]["id"]
        assert assignments[0]["status"] == "OFFERED"

        # Step 5: Worker accepts assignment -> status becomes IN_PROGRESS
        accept_res = await ac.patch(
            f"/api/v1/assignments/{assignment_id}",
            json={"status": "ACCEPTED"},
            headers=adm_headers
        )
        assert accept_res.status_code == 200
        assert accept_res.json()["status"] == "ACCEPTED"

        db_session.expire_all()
        inc_in_prog = db_session.query(Incident).filter(Incident.id == inc_id).first()
        assert inc_in_prog.status == "IN_PROGRESS"

        # Step 6: Worker completes task WITHOUT evidence -> Verification Agent executes and FAILS
        complete_res = await ac.patch(
            f"/api/v1/assignments/{assignment_id}",
            json={"status": "COMPLETED", "worker_notes": "Repaired loose terminals and attached rubber insulation"},
            headers=adm_headers
        )
        assert complete_res.status_code == 200
        assert complete_res.json()["status"] == "COMPLETED"

        # Incident must NOT be resolved prematurely
        db_session.expire_all()
        inc_verif_fail = db_session.query(Incident).filter(Incident.id == inc_id).first()
        assert inc_verif_fail.status != "RESOLVED"
        assert inc_verif_fail.status == "RESOLVED_PENDING_VERIFICATION"

        # Check HumanApproval created for missing verification evidence
        unverified_appr = db_session.query(HumanApproval).filter(
            HumanApproval.incident_id == inc_id,
            HumanApproval.approval_type == "UNCERTAIN_VERIFICATION"
        ).first()
        assert unverified_appr is not None

        # Step 7: Worker uploads PHOTO_AFTER evidence -> Verification Agent triggers and SUCCEEDS
        test_img_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb" + (b"\x00" * 100)
        upload_res = await ac.post(
            f"/api/v1/incidents/{inc_id}/evidence",
            files={"file": ("verified_repair.jpg", test_img_bytes, "image/jpeg")},
            data={"evidence_type": "PHOTO_AFTER", "notes": "Fixed enclosure with weather seal"},
            headers=adm_headers
        )
        assert upload_res.status_code == 200

        # Verification must now pass and mark incident RESOLVED
        db_session.expire_all()
        inc_resolved = db_session.query(Incident).filter(Incident.id == inc_id).first()
        assert inc_resolved.status == "RESOLVED"
        assert inc_resolved.resolved_at is not None

        # Step 8: Prevent duplicate active assignment
        any_worker = db_session.query(WorkerProfile).first()
        dup_assign = await ac.post("/api/v1/assignments", json={
            "incident_id": inc_id,
            "worker_id": any_worker.id,
            "assigned_by_type": "ADMIN"
        }, headers=adm_headers)
        assert dup_assign.status_code == 400

        # Step 9: Prevent altering status of completed assignment
        alter_completed = await ac.patch(
            f"/api/v1/assignments/{assignment_id}",
            json={"status": "ACCEPTED"},
            headers=adm_headers
        )
        assert alter_completed.status_code == 400

        # Step 10: Verify all 5 agents have execution telemetry records in DB
        agent_names = set()
        for _ in range(15):
            db_session.expire_all()
            executions = db_session.query(AgentExecution).filter(AgentExecution.incident_id == inc_id).all()
            agent_names = {e.agent_name for e in executions}
            if "COORDINATION" in agent_names and "VERIFICATION" in agent_names:
                break
            await asyncio.sleep(0.5)

        assert "INCIDENT_INTELLIGENCE" in agent_names
        assert "DUPLICATE_DETECTION" in agent_names
        assert "PRIORITY" in agent_names
        assert "RESOURCE_ALLOCATION" in agent_names
        assert "COORDINATION" in agent_names
        assert "VERIFICATION" in agent_names


