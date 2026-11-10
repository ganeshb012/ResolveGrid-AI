import logging
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from backend.app.db.session import engine, Base, SessionLocal
from backend.app.core.security import get_password_hash
from backend.app.models.entities import (
    User,
    Department,
    CitizenProfile,
    WorkerProfile,
    WorkerAvailability,
    Incident,
    IncidentReport,
    Assignment,
    IncidentStatusHistory,
    Notification,
    HumanApproval,
    AgentExecution,
    utc_now,
)

logger = logging.getLogger("resolvegrid.seed")


def seed_database():
    """Initializes tables and seeds demo departments, users, workers, and incidents around Pune."""
    # Create all tables if not exist
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        # Check if already seeded
        if db.query(User).filter(User.email == "admin@resolvegrid.gov.in").first():
            logger.info("Database already seeded.")
            return

        logger.info("Seeding database with Pune demo infrastructure data...")

        # 1. Departments
        departments_data = [
            {"code": "ROADS", "name": "Roads & Highway Maintenance", "description": "Handles pothole repairs, tarring, speed bumps and road resurfacing"},
            {"code": "WATER", "name": "Water Supply & Distribution", "description": "Manages municipal water lines, main pipe leaks, and potable water delivery"},
            {"code": "ELECTRICAL", "name": "Electrical & Street Lighting", "description": "Maintains streetlights, public transformers, and electrical poles"},
            {"code": "SANITATION", "name": "Solid Waste & Sanitation", "description": "Garbage disposal, neighborhood bins, public hygiene and trash clearing"},
            {"code": "DRAINAGE", "name": "Stormwater & Drainage Division", "description": "Open manholes, stormwater gutters, and monsoon drainage systems"},
            {"code": "GENERAL", "name": "General Public Infrastructure", "description": "General civic issues and unclassified public infrastructure reports"}
        ]

        dept_map = {}
        for d_info in departments_data:
            dept = Department(
                id=str(uuid.uuid4()),
                code=d_info["code"],
                name=d_info["name"],
                description=d_info["description"],
                contact_email=f"{d_info['code'].lower()}@resolvegrid.gov.in",
                contact_phone="+91 20 2550 1000",
                is_active=True
            )
            db.add(dept)
            dept_map[d_info["code"]] = dept

        db.flush()

        # 2. Users
        # Admin
        admin = User(
            id=str(uuid.uuid4()),
            email="admin@resolvegrid.gov.in",
            password_hash=get_password_hash("Admin@12345"),
            full_name="Rajesh Sharma (Chief Operations Officer)",
            phone="+91 98220 11000",
            role="ADMIN",
            preferred_language="en",
            is_active=True
        )
        db.add(admin)

        # Citizen 1
        citizen1 = User(
            id=str(uuid.uuid4()),
            email="citizen@resolvegrid.gov.in",
            password_hash=get_password_hash("Citizen@12345"),
            full_name="Aarav Deshmukh",
            phone="+91 94220 33441",
            role="CITIZEN",
            preferred_language="mr",
            is_active=True
        )
        db.add(citizen1)
        db.flush()

        c_profile1 = CitizenProfile(
            id=str(uuid.uuid4()),
            user_id=citizen1.id,
            address="Flat 402, Kothrud Heights, Paud Road, Pune"
        )
        db.add(c_profile1)

        # Citizen 2
        citizen2 = User(
            id=str(uuid.uuid4()),
            email="priya.patil@resolvegrid.gov.in",
            password_hash=get_password_hash("Citizen@12345"),
            full_name="Priya Patil",
            phone="+91 97650 99882",
            role="CITIZEN",
            preferred_language="en",
            is_active=True
        )
        db.add(citizen2)
        db.flush()

        # 3. Field Workers across Pune
        worker_specs = [
            {
                "email": "worker@resolvegrid.gov.in",
                "name": "Suresh Kadam (Roads Specialist)",
                "dept": "ROADS",
                "emp_id": "PUMC-RD-101",
                "skills": "Asphalt patch, heavy machinery, road resurfacing",
                "lat": 18.5080, "lon": 73.8100,  # Kothrud
                "status": "AVAILABLE"
            },
            {
                "email": "water.worker@resolvegrid.gov.in",
                "name": "Amit Jadhav (Hydraulic Technician)",
                "dept": "WATER",
                "emp_id": "PUMC-WT-204",
                "skills": "Pipeline welding, valve replacement, high pressure piping",
                "lat": 18.5320, "lon": 73.8450,  # Shivajinagar
                "status": "AVAILABLE"
            },
            {
                "email": "electric.worker@resolvegrid.gov.in",
                "name": "Vikram Shinde (Electrical Lineman)",
                "dept": "ELECTRICAL",
                "emp_id": "PUMC-EL-308",
                "skills": "High-voltage transmission, LED street lights, junction boxes",
                "lat": 18.5680, "lon": 73.9150,  # Viman Nagar
                "status": "AVAILABLE"
            },
            {
                "email": "drainage.worker@resolvegrid.gov.in",
                "name": "Ganesh More (Drainage Supervisor)",
                "dept": "DRAINAGE",
                "emp_id": "PUMC-DR-412",
                "skills": "Manhole cover replacement, desilting, culvert repair",
                "lat": 18.5020, "lon": 73.8640,  # Swargate
                "status": "AVAILABLE"
            },
            {
                "email": "sanitation.worker@resolvegrid.gov.in",
                "name": "Sunil Gaikwad (Sanitation Officer)",
                "dept": "SANITATION",
                "emp_id": "PUMC-SN-515",
                "skills": "Waste compactor operation, dump site clearance",
                "lat": 18.5595, "lon": 73.7870,  # Baner
                "status": "AVAILABLE"
            }
        ]

        worker_objects = []
        for ws in worker_specs:
            w_user = User(
                id=str(uuid.uuid4()),
                email=ws["email"],
                password_hash=get_password_hash("Worker@12345"),
                full_name=ws["name"],
                phone="+91 99210 " + str(uuid.uuid4().int)[:5],
                role="WORKER",
                preferred_language="mr",
                is_active=True
            )
            db.add(w_user)
            db.flush()

            w_profile = WorkerProfile(
                id=str(uuid.uuid4()),
                user_id=w_user.id,
                department_id=dept_map[ws["dept"]].id,
                employee_id=ws["emp_id"],
                skills=ws["skills"],
                current_latitude=ws["lat"],
                current_longitude=ws["lon"],
                last_location_update=utc_now(),
                is_on_duty=True,
                current_active_tasks=0
            )
            db.add(w_profile)
            db.flush()

            w_avail = WorkerAvailability(
                id=str(uuid.uuid4()),
                worker_id=w_profile.id,
                status=ws["status"],
                notes="Ready for automated smart dispatch",
                updated_at=utc_now()
            )
            db.add(w_avail)
            worker_objects.append(w_profile)

        db.flush()

        # 4. Realistic Demo Incidents in Pune
        incidents_data = [
            {
                "num": "INC-PN-1001",
                "title": "Severe Pothole Cluster on Paud Road",
                "desc": "Multiple deep potholes near Kothrud bus depot causing frequent scooter skidding and evening traffic slowdown.",
                "cat": "ROAD_POTHOLE",
                "prio": "HIGH",
                "status": "IN_PROGRESS",
                "lat": 18.5074, "lon": 73.8077,
                "addr": "Near Kothrud Stand, Paud Road, Pune 411038",
                "dept": "ROADS",
                "reporter": citizen1.id,
                "worker": worker_objects[0]
            },
            {
                "num": "INC-PN-1002",
                "title": "Water Main Leakage near Ferguson College Road",
                "desc": "Fresh drinking water pipeline leaking continuously onto FC Road pavement. Water is gushing onto the pedestrian footpath.",
                "cat": "WATER_LEAKAGE",
                "prio": "HIGH",
                "status": "ASSIGNED",
                "lat": 18.5196, "lon": 73.8410,
                "addr": "Near Goodluck Chowk, FC Road, Shivajinagar, Pune 411004",
                "dept": "WATER",
                "reporter": citizen2.id,
                "worker": worker_objects[1]
            },
            {
                "num": "INC-PN-1003",
                "title": "Uncovered Open Manhole on Swargate Junction",
                "desc": "Cast iron cover missing on stormwater drain chamber right next to pedestrian zebra crossing. Extreme accident risk.",
                "cat": "OPEN_MANHOLE",
                "prio": "CRITICAL",
                "status": "PENDING_APPROVAL",
                "lat": 18.5018, "lon": 73.8636,
                "addr": "Jedhe Chowk, Swargate Bus Terminal, Pune 411042",
                "dept": "DRAINAGE",
                "reporter": citizen1.id,
                "worker": None
            },
            {
                "num": "INC-PN-1004",
                "title": "Streetlight Grid Outage in Viman Nagar Sector 2",
                "desc": "5 consecutive street lamp posts non-functional along Dutta Mandir road. Complete darkness posing safety concerns at night.",
                "cat": "STREETLIGHT",
                "prio": "MEDIUM",
                "status": "RESOLVED",
                "lat": 18.5679, "lon": 73.9143,
                "addr": "Dutta Mandir Road, Near Symbiosis, Viman Nagar, Pune 411014",
                "dept": "ELECTRICAL",
                "reporter": citizen2.id,
                "worker": worker_objects[2]
            },
            {
                "num": "INC-PN-1005",
                "title": "Garbage Overflow at Baner Hill Footpath",
                "desc": "Municipal community waste bin overflowing across 15 meters of public walkway with stray animal gathering.",
                "cat": "GARBAGE_OVERFLOW",
                "prio": "MEDIUM",
                "status": "REPORTED",
                "lat": 18.5590, "lon": 73.7868,
                "addr": "Baner - Pashan Link Road, Pune 411045",
                "dept": "SANITATION",
                "reporter": citizen1.id,
                "worker": None
            }
        ]

        for inc_info in incidents_data:
            inc = Incident(
                id=str(uuid.uuid4()),
                incident_number=inc_info["num"],
                title=inc_info["title"],
                description=inc_info["desc"],
                category=inc_info["cat"],
                priority=inc_info["prio"],
                status=inc_info["status"],
                latitude=inc_info["lat"],
                longitude=inc_info["lon"],
                address=inc_info["addr"],
                reported_by_id=inc_info["reporter"],
                department_id=dept_map[inc_info["dept"]].id,
                confidence_score=0.96,
                public_safety_risk=(inc_info["prio"] == "CRITICAL"),
                requires_human_approval=(inc_info["status"] == "PENDING_APPROVAL"),
                created_at=utc_now() - timedelta(hours=4),
                resolved_at=(utc_now() - timedelta(hours=1)) if inc_info["status"] == "RESOLVED" else None
            )
            db.add(inc)
            db.flush()

            # Status history
            db.add(IncidentStatusHistory(
                id=str(uuid.uuid4()),
                incident_id=inc.id,
                old_status=None,
                new_status="REPORTED",
                change_reason="Reported by citizen through ResolveGrid Portal",
                trigger_type="CITIZEN",
                timestamp=inc.created_at
            ))

            if inc_info["status"] in ["ASSIGNED", "IN_PROGRESS", "RESOLVED"]:
                db.add(IncidentStatusHistory(
                    id=str(uuid.uuid4()),
                    incident_id=inc.id,
                    old_status="REPORTED",
                    new_status="CLASSIFIED",
                    change_reason="Automated classification completed by Incident Intelligence Agent",
                    trigger_type="AGENT",
                    timestamp=inc.created_at + timedelta(minutes=2)
                ))

            # Assignment if worker assigned
            if inc_info["worker"]:
                w = inc_info["worker"]
                w.current_active_tasks += 1
                assign = Assignment(
                    id=str(uuid.uuid4()),
                    incident_id=inc.id,
                    worker_id=w.id,
                    assigned_by_type="AGENT",
                    status="ACCEPTED" if inc_info["status"] in ["IN_PROGRESS", "RESOLVED"] else "OFFERED",
                    offered_at=inc.created_at + timedelta(minutes=5),
                    responded_at=inc.created_at + timedelta(minutes=8),
                    started_at=inc.created_at + timedelta(minutes=15),
                    completed_at=(inc.created_at + timedelta(hours=3)) if inc_info["status"] == "RESOLVED" else None,
                    worker_distance_km=2.4,
                    worker_notes="Work completed on schedule with heavy patch material" if inc_info["status"] == "RESOLVED" else "Dispatched to site"
                )
                db.add(assign)

            # If pending approval, create human approval request
            if inc_info["status"] == "PENDING_APPROVAL":
                appr = HumanApproval(
                    id=str(uuid.uuid4()),
                    incident_id=inc.id,
                    approval_type="HIGH_PRIORITY_ESCALATION",
                    requested_by_agent="PRIORITY",
                    reason="Critical public safety hazard: open manhole adjacent to high-traffic bus terminal.",
                    context_data="{}",
                    status="PENDING",
                    created_at=utc_now() - timedelta(hours=1)
                )
                db.add(appr)

            # Seed an AgentExecution record for AI Activity Center
            exec_rec = AgentExecution(
                id=str(uuid.uuid4()),
                incident_id=inc.id,
                workflow_run_id=f"run_seed_{inc.incident_number}",
                agent_name="INCIDENT_INTELLIGENCE",
                status="COMPLETED",
                input_payload=f'{{"title": "{inc.title}", "description": "{inc.description}"}}',
                output_payload=f'{{"category": "{inc.category}", "confidence": 0.96}}',
                reasoning_summary=f"Parsed incident report, classified category as {inc.category} under {inc_info['dept']}.",
                latency_ms=185,
                started_at=inc.created_at,
                completed_at=inc.created_at + timedelta(seconds=1)
            )
            db.add(exec_rec)

        db.commit()
        logger.info("Database seeding successfully completed!")
    except Exception as e:
        db.rollback()
        logger.error("Error during database seeding: %s", str(e), exc_info=True)
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
