# ResolveGrid AI — Complete Multi-Agent Incident Resolution Platform

**ResolveGrid AI** is an enterprise-grade agentic platform for autonomous public infrastructure incident resolution in smart cities (demonstrated with realistic coordinates in Pune, Maharashtra).

It coordinates the complete incident lifecycle:
> Citizen voice/text reporting → Automatic speech-to-text (Gnani Prisma) → Incident classification & entity extraction (Gnani Evon) → Proximity duplicate detection → Priority & hazard assessment → Department identification → Worker allocation via Haversine proximity calculations → Voice dispatch coordination (Gnani Timbre) → Progress monitoring & SLA escalation → Photographic evidence verification → Incident closure & citizen notification.

---

## 🏛️ System Architecture

ResolveGrid AI is built as **ONE integrated full-stack application** containing **FOUR connected interfaces** and **FIVE specialized LangGraph agents**:

### 1. The Four Integrated Interfaces

- **Citizen Portal (`/citizen`)**:
  - Multilingual interface supporting **Marathi (मराठी)**, **Hindi (हिन्दी)**, and **English**.
  - Voice-based reporting with browser MediaRecorder and **Gnani Prisma** Speech-to-Text transcription.
  - Interactive **Leaflet & OpenStreetMap** location pin selector with Pune landmarks (Kothrud, Shivajinagar, Swargate, Baner, Viman Nagar, Hinjewadi).
  - Live complaint tracking timeline with status badges.
  - One-click voice status updates synthesized via **Gnani Timbre** Text-to-Speech.
- **Operations Command Dashboard (`/admin`)**:
  - Real-time KPI statistics (Total, In Progress, Critical Hazards, Resolved, Escalated, Available Crews).
  - Interactive Leaflet incident & worker map with styled markers, priority indicators, and worker availability pins.
  - Incident management table with search, category filtering, and manual worker dispatch.
  - Department resolution load and priority breakdown charts using **Recharts**.
  - **Human Approval Queue**: review and approve/reject high-risk escalations, unusual allocations, and uncertain verifications.
- **Field Crew Hub (`/worker`)**:
  - Worker profile with employee ID, skills, department, and duty status toggle (Available, Busy, On Break, Off Duty).
  - Assigned task queue with priority badges, address, and Haversine distance from worker's current coordinates.
  - Accept or reject assignments (with mandatory reason triggering automated escalation).
  - Voice instruction playback synthesized by Gnani Timbre.
  - Photographic completion evidence upload (`PHOTO_AFTER`) with field notes.
  - Triggers Verification Agent upon work completion.
- **AI Multi-Agent Center (`/admin/ai-activity`)**:
  - Integrated into the Admin application.
  - Displays all 5 specialized agents with execution status, latency in milliseconds, and run counters.
  - Live WebSocket stream of agent actions.
  - Interactive tool call inspector showing tool names (`find_similar_incidents`, `classify_incident`, `calculate_priority`, `get_available_workers`, `assign_worker`, `notify_worker`, `verify_resolution`, `request_human_approval`), exact structured inputs, and outputs.
  - Concise user-facing decision explanations (strictly avoiding private chain-of-thought exposure).

---

## 🤖 The Five LangGraph Agents & Tools

The backend orchestrates a coordinated state graph (`StateGraph(AgentState)`):

1. **Incident Intelligence Agent (`INCIDENT_INTELLIGENCE`)**:
   - Parses multimodal speech and text inputs.
   - Detects duplicate incidents within 250m using Haversine proximity checks to prevent duplicate municipal dispatch.
   - Invokes `classify_incident()` and extracts structured entities (category, department code, safety risk).
2. **Priority Agent (`PRIORITY`)**:
   - Assesses public safety risks, water leakage severity, traffic disruption, and crater depth.
   - Assigns priority (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
   - Flags critical incidents for human oversight.
3. **Resource Allocation Agent (`RESOURCE_ALLOCATION`)**:
   - Matches the responsible department (`ROADS`, `WATER`, `ELECTRICAL`, `SANITATION`, `DRAINAGE`, `GENERAL`).
   - Queries on-duty workers and calculates real-time distances using **Haversine formula**.
   - Selects the optimal field worker based on distance and active workload.
   - Enqueues human approval if no worker is within range.
4. **Coordination Agent (`COORDINATION`)**:
   - Generates outbound voice instructions using **Gnani Timbre**.
   - Dispatches WebSocket alerts and mobile notifications to assigned workers.
   - Notifies the reporting citizen with synthesized voice updates.
   - Schedules background SLA monitoring for acknowledgment timeouts.
5. **Verification Agent (`VERIFICATION`)**:
   - Reviews submitted resolution proof (`PHOTO_AFTER` photographic evidence and worker notes).
   - Validates that resolution criteria are met before closing complaints.
   - Escalates uncertain or missing evidence to the admin Human Approval Queue.

---

## 🎙️ Gnani AI Model Integrations

Located in `backend/app/integrations/gnani/`:
- **Prisma (`prisma.py`)**: Speech-to-Text for Marathi, Hindi, and English voice complaint recording.
- **Evon (`evon.py`)**: Language and reasoning engine driving classification, entity extraction, and prioritization.
- **Timbre (`timbre.py`)**: Text-to-Speech generating spoken voice updates for citizens and worker dispatch audio.
- **Warp (`warp.py`)**: Real-time conversational speech-to-speech interaction.

*Configuration Policy*:
Credentials are read from environment variables (`GNANI_API_KEY`, `GNANI_PRISMA_URL`, etc.). When live credentials are not yet supplied, the typed adapter gracefully falls back to deterministic simulation mode (`GNANI_MOCK_FALLBACK=true`), ensuring the entire multi-agent lifecycle and UI remain fully demonstrable and testable locally without faking external API successes.

---

## 💾 Database & Background Tasks (No Docker Required)

- **Database**: SQLite at `backend/data/resolvegrid.db`.
  - Configured with `PRAGMA foreign_keys = ON` and `PRAGMA journal_mode = WAL`.
  - Full **Alembic** migration history (`alembic upgrade head`).
  - Python **Haversine calculations** for geographic proximity.
- **Background Tasks**:
  - Automatic broker detection: checks for local Redis/Memurai service.
  - If Redis is absent, automatically activates an asynchronous recoverable task runner with task retries, worker voice notifications, and periodic escalation sweeps.

---

## 🚀 Running ResolveGrid AI Locally (Windows PowerShell)

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm

### 1. Start FastAPI Backend
```powershell
.\run-backend.ps1
```
*Or manually:*
```powershell
.\backend\.venv\Scripts\uvicorn.exe backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
- API Documentation (Swagger): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Platform Health Status: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### 2. Start Vite Frontend
In a separate terminal:
```powershell
.\run-frontend.ps1
```
*Or manually:*
```powershell
cd frontend
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

### 3. Run the Pytest Verification Suite
```powershell
.\run-tests.ps1
```
*Or manually:*
```powershell
.\backend\.venv\Scripts\pytest -v
```

---

## 🔑 Pre-Seeded Demonstration Accounts

For instant testing, use the **Quick Demo Switcher** in the top navigation bar or log in with:

| Role | Email | Password | Access & Features |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@resolvegrid.gov.in` | `Admin@12345` | Operations Command, Map, Dispatch, Approval Queue, AI Center |
| **Citizen** | `citizen@resolvegrid.gov.in` | `Citizen@12345` | Multilingual Voice Reporting, Leaflet Map Picker, Live Tracking |
| **Field Worker** | `worker@resolvegrid.gov.in` | `Worker@12345` | Task Queue, Accept/Reject, Photo Evidence Upload, Notes |

