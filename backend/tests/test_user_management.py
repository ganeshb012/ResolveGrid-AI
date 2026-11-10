import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.models.entities import User, Department, WorkerProfile, CitizenProfile


@pytest.mark.asyncio
async def test_citizen_self_registration_success():
    """Test citizen self-registration creates account with CITIZEN role and profile."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"citizen_new_{uuid.uuid4().hex[:6]}@example.com"
        res = await ac.post("/api/v1/auth/register", json={
            "full_name": "Rohan Joshi",
            "email": email,
            "phone": "+91 98221 11222",
            "password": "CitizenSecret@123",
            "preferred_language": "mr"
        })
        assert res.status_code == 201
        data = res.json()
        assert data["role"] == "CITIZEN"
        assert data["email"] == email.lower()
        assert "access_token" in data

        # Check DB
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == email.lower()).first()
            assert user is not None
            assert user.role == "CITIZEN"
            assert user.is_active is True
            assert user.citizen_profile is not None
        finally:
            db.close()


@pytest.mark.asyncio
async def test_public_admin_or_worker_registration_rejected():
    """Ensure public registration rejects any attempt to register as ADMIN or WORKER."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Attempt public ADMIN registration
        admin_res = await ac.post("/api/v1/auth/register", json={
            "full_name": "Hacker Admin",
            "email": f"hacker_admin_{uuid.uuid4().hex[:6]}@example.com",
            "password": "Password123",
            "role": "ADMIN"
        })
        assert admin_res.status_code == 400
        assert "exclusively to new citizen accounts" in admin_res.json()["detail"]

        # Attempt public WORKER registration
        worker_res = await ac.post("/api/v1/auth/register", json={
            "full_name": "Unauthorized Worker",
            "email": f"unauth_worker_{uuid.uuid4().hex[:6]}@example.com",
            "password": "Password123",
            "role": "WORKER"
        })
        assert worker_res.status_code == 400
        assert "exclusively to new citizen accounts" in worker_res.json()["detail"]


@pytest.mark.asyncio
async def test_duplicate_email_registration_rejected():
    """Ensure duplicate email registration is rejected with HTTP 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        dup_email = f"dup_{uuid.uuid4().hex[:6]}@example.com"
        res1 = await ac.post("/api/v1/auth/register", json={
            "full_name": "Original User",
            "email": dup_email,
            "password": "Password123"
        })
        assert res1.status_code == 201

        res2 = await ac.post("/api/v1/auth/register", json={
            "full_name": "Duplicate User",
            "email": dup_email,
            "password": "Password123"
        })
        assert res2.status_code == 400
        assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_admin_user_management_rbac():
    """Test RBAC protection on /api/v1/users: Admin allowed, Citizen & Worker denied."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Admin login
        adm_login = await ac.post("/api/v1/auth/login", json={
            "email": "admin@resolvegrid.gov.in",
            "password": "Admin@12345"
        })
        adm_token = adm_login.json()["access_token"]
        adm_headers = {"Authorization": f"Bearer {adm_token}"}

        # Citizen login
        cit_login = await ac.post("/api/v1/auth/login", json={
            "email": "citizen@resolvegrid.gov.in",
            "password": "Citizen@12345"
        })
        cit_token = cit_login.json()["access_token"]
        cit_headers = {"Authorization": f"Bearer {cit_token}"}

        # Worker login
        wrk_login = await ac.post("/api/v1/auth/login", json={
            "email": "worker@resolvegrid.gov.in",
            "password": "Worker@12345"
        })
        wrk_token = wrk_login.json()["access_token"]
        wrk_headers = {"Authorization": f"Bearer {wrk_token}"}

        # Citizen cannot access /api/v1/users
        cit_get = await ac.get("/api/v1/users", headers=cit_headers)
        assert cit_get.status_code == 403

        # Worker cannot access /api/v1/users
        wrk_get = await ac.get("/api/v1/users", headers=wrk_headers)
        assert wrk_get.status_code == 403

        # Admin CAN access /api/v1/users
        adm_get = await ac.get("/api/v1/users", headers=adm_headers)
        assert adm_get.status_code == 200
        assert isinstance(adm_get.json(), list)


@pytest.mark.asyncio
async def test_admin_create_field_crew_and_manage_lifecycle():
    """Test Admin creates Field Crew account, edits department, resets password, and tests deactivation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Admin login
        adm_login = await ac.post("/api/v1/auth/login", json={
            "email": "admin@resolvegrid.gov.in",
            "password": "Admin@12345"
        })
        adm_headers = {"Authorization": f"Bearer {adm_login.json()['access_token']}"}

        # Fetch departments
        depts_res = await ac.get("/api/v1/users/departments", headers=adm_headers)
        assert depts_res.status_code == 200
        depts = depts_res.json()
        assert len(depts) >= 1
        dept_id = depts[0]["id"]

        # Admin creates new Field Crew member
        worker_email = f"field_crew_{uuid.uuid4().hex[:6]}@resolvegrid.gov.in"
        create_res = await ac.post("/api/v1/users", json={
            "role": "WORKER",
            "full_name": "Mahesh Patil",
            "email": worker_email,
            "phone": "+91 97654 32100",
            "password": "WorkerInitial@123",
            "department_id": dept_id,
            "employee_id": f"EMP-TST-{uuid.uuid4().hex[:4].upper()}",
            "skills": "Electrical grid & streetlight diagnosis"
        }, headers=adm_headers)
        assert create_res.status_code == 201
        created_user = create_res.json()
        user_id = created_user["id"]
        assert created_user["role"] == "WORKER"
        assert created_user["full_name"] == "Mahesh Patil"
        assert created_user["is_active"] is True

        # Worker can log in with initial credentials
        worker_login = await ac.post("/api/v1/auth/login", json={
            "email": worker_email,
            "password": "WorkerInitial@123"
        })
        assert worker_login.status_code == 200
        assert worker_login.json()["role"] == "WORKER"

        # Admin updates worker details (skills and phone)
        update_res = await ac.patch(f"/api/v1/users/{user_id}", json={
            "full_name": "Mahesh R. Patil",
            "skills": "Senior Master Electrician, Transformer Repair"
        }, headers=adm_headers)
        assert update_res.status_code == 200
        assert update_res.json()["full_name"] == "Mahesh R. Patil"
        assert update_res.json()["skills"] == "Senior Master Electrician, Transformer Repair"

        # Admin resets worker password
        reset_res = await ac.post(f"/api/v1/users/{user_id}/reset-password", json={
            "new_password": "NewSecretWorkerPassword@999"
        }, headers=adm_headers)
        assert reset_res.status_code == 200
        assert reset_res.json()["status"] == "SUCCESS"

        # Worker logs in with new password
        login_new_pw = await ac.post("/api/v1/auth/login", json={
            "email": worker_email,
            "password": "NewSecretWorkerPassword@999"
        })
        assert login_new_pw.status_code == 200

        # Old password rejected
        login_old_pw = await ac.post("/api/v1/auth/login", json={
            "email": worker_email,
            "password": "WorkerInitial@123"
        })
        assert login_old_pw.status_code == 401

        # Admin deactivates worker
        deactivate_res = await ac.patch(f"/api/v1/users/{user_id}", json={
            "is_active": False
        }, headers=adm_headers)
        assert deactivate_res.status_code == 200
        assert deactivate_res.json()["is_active"] is False

        # Deactivated worker login rejected with 403
        login_deactivated = await ac.post("/api/v1/auth/login", json={
            "email": worker_email,
            "password": "NewSecretWorkerPassword@999"
        })
        assert login_deactivated.status_code == 403
        assert "deactivated" in login_deactivated.json()["detail"].lower()


@pytest.mark.asyncio
async def test_last_admin_lockout_prevention():
    """Ensure an administrator cannot deactivate the last remaining active admin."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        adm_login = await ac.post("/api/v1/auth/login", json={
            "email": "admin@resolvegrid.gov.in",
            "password": "Admin@12345"
        })
        adm_headers = {"Authorization": f"Bearer {adm_login.json()['access_token']}"}
        adm_user_id = adm_login.json()["user_id"]

        db = SessionLocal()
        try:
            # Deactivate any other admins in DB so only 1 active admin remains
            other_admins = db.query(User).filter(
                User.role == "ADMIN",
                User.id != adm_user_id
            ).all()
            for o in other_admins:
                o.is_active = False
            db.commit()
        finally:
            db.close()

        # Attempt to deactivate the only remaining admin
        deact_res = await ac.patch(f"/api/v1/users/{adm_user_id}", json={
            "is_active": False
        }, headers=adm_headers)
        assert deact_res.status_code == 400
        assert "last remaining active administrator" in deact_res.json()["detail"]
