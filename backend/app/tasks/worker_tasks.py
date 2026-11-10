import logging
from datetime import datetime, timezone, timedelta
from backend.app.core.config import settings
from backend.app.db.session import SessionLocal
from backend.app.models.entities import (
    Incident, Assignment, Notification, User, WorkerProfile, IncidentStatusHistory, utc_now
)
from backend.app.integrations.gnani.timbre import TimbreTTSAdapter
from backend.app.integrations.gnani.schemas import TimbreSynthesizeRequest
from backend.app.websockets.manager import ws_manager
from backend.app.tasks.manager import TaskRegistry
from backend.app.tasks.celery_app import celery_app

logger = logging.getLogger("resolvegrid.tasks.worker_tasks")


@TaskRegistry.register("dispatch_worker_voice_notification")
async def dispatch_worker_voice_notification(assignment_id: str, worker_id: str, message: str, language: str = "en"):
    """Generate audio instruction with Timbre and create a notification for the worker."""
    db = SessionLocal()
    try:
        worker = db.query(WorkerProfile).filter(WorkerProfile.id == worker_id).first()
        if not worker or not worker.user:
            logger.warning("Worker profile %s not found for notification", worker_id)
            return

        # Synthesize audio with Timbre
        tts = TimbreTTSAdapter()
        audio_url = None
        try:
            tts_res = await tts.synthesize(TimbreSynthesizeRequest(
                text=message,
                language=language,
                voice_gender="neutral"
            ))
            audio_url = tts_res.audio_url
        except Exception as e:
            logger.warning("Voice synthesis for worker failed: %s", str(e))

        notification = Notification(
            recipient_id=worker.user.id,
            channel="VOICE_TIMBRE" if audio_url else "IN_APP",
            title="New Incident Assignment Dispatched",
            message=message,
            audio_file_path=audio_url,
            language=language,
            status="SENT",
            sent_at=utc_now()
        )
        db.add(notification)
        db.commit()

        # Send live WebSocket alert to worker
        await ws_manager.send_to_user(
            worker.user.id,
            "NEW_ASSIGNMENT_ALERT",
            {
                "assignment_id": assignment_id,
                "title": "New Incident Assignment",
                "message": message,
                "audio_url": audio_url
            }
        )
        logger.info("Dispatched voice notification to worker %s (Audio: %s)", worker.user.email, audio_url)
    finally:
        db.close()


@TaskRegistry.register("dispatch_citizen_status_update")
async def dispatch_citizen_status_update(incident_id: str, citizen_id: str, title: str, message: str, language: str = "en"):
    """Notify citizen of status change with Timbre voice audio."""
    db = SessionLocal()
    try:
        citizen = db.query(User).filter(User.id == citizen_id).first()
        if not citizen:
            return

        tts = TimbreTTSAdapter()
        audio_url = None
        try:
            tts_res = await tts.synthesize(TimbreSynthesizeRequest(
                text=message,
                language=language
            ))
            audio_url = tts_res.audio_url
        except Exception as e:
            logger.warning("Voice synthesis for citizen failed: %s", str(e))

        notification = Notification(
            recipient_id=citizen.id,
            incident_id=incident_id,
            channel="VOICE_TIMBRE" if audio_url else "IN_APP",
            title=title,
            message=message,
            audio_file_path=audio_url,
            language=language,
            status="SENT",
            sent_at=utc_now()
        )
        db.add(notification)
        db.commit()

        await ws_manager.send_to_user(
            citizen.id,
            "CITIZEN_STATUS_UPDATE",
            {
                "incident_id": incident_id,
                "title": title,
                "message": message,
                "audio_url": audio_url
            }
        )
        logger.info("Citizen %s notified for incident %s", citizen.email, incident_id)
    finally:
        db.close()


@TaskRegistry.register("check_assignment_acknowledgement")
async def check_assignment_acknowledgement(assignment_id: str):
    """Check if worker acknowledged the task within timeout; if not, escalate or reassign."""
    db = SessionLocal()
    try:
        assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if not assignment or assignment.status != "OFFERED":
            return  # Already accepted, rejected, or completed

        logger.warning("Assignment %s timed out with no response from worker", assignment_id)
        assignment.status = "REJECTED"
        assignment.rejection_reason = "Automated timeout: worker did not acknowledge within window."
        assignment.responded_at = utc_now()

        # Update incident status
        incident = assignment.incident
        if incident and incident.status == "ASSIGNED":
            incident.status = "ESCALATED"
            incident.urgency_reason = "Assigned worker did not respond within required SLA window."
            history = IncidentStatusHistory(
                incident_id=incident.id,
                old_status="ASSIGNED",
                new_status="ESCALATED",
                change_reason="Automated timeout: worker did not respond.",
                trigger_type="AGENT"
            )
            db.add(history)

        db.commit()
        await ws_manager.broadcast("INCIDENT_ESCALATED", {
            "incident_id": incident.id,
            "reason": "Worker acknowledgment timeout"
        })
    finally:
        db.close()


@TaskRegistry.register("periodic_escalation_sweep")
async def periodic_escalation_sweep():
    """Background check for critical incidents that have remained unassigned or overdue."""
    db = SessionLocal()
    try:
        critical_unassigned = db.query(Incident).filter(
            Incident.priority.in_(["CRITICAL", "HIGH"]),
            Incident.status.in_(["REPORTED", "CLASSIFIED"]),
            Incident.created_at < (utc_now() - timedelta(minutes=30))
        ).all()

        for inc in critical_unassigned:
            logger.info("Auto-escalating high priority unassigned incident %s", inc.incident_number)
            inc.status = "ESCALATED"
            inc.requires_human_approval = True
            db.add(IncidentStatusHistory(
                incident_id=inc.id,
                old_status="REPORTED",
                new_status="ESCALATED",
                change_reason="Auto-escalation: high-priority incident unattended for over 30 minutes.",
                trigger_type="AGENT"
            ))

        db.commit()
    except Exception as e:
        logger.error("Error in periodic_escalation_sweep: %s", str(e))
    finally:
        db.close()


@celery_app.task(name="execute_celery_task")
def execute_celery_task(task_name: str, kwargs: dict):
    """Celery worker bridge."""
    import asyncio
    handler = TaskRegistry.get(task_name)
    if not handler:
        logger.error("Celery task handler not found: %s", task_name)
        return False
    if asyncio.iscoroutinefunction(handler):
        asyncio.run(handler(**kwargs))
    else:
        handler(**kwargs)
    return True
