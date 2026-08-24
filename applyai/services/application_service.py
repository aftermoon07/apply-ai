"""Application Service with strict state machine validation."""

import logging
from applyai.core.database import get_session
from applyai.models.application import Application
from applyai.models.event import EventType
from applyai.services.event_service import EventService
from sqlalchemy import select

logger = logging.getLogger(__name__)

# Valid transitions
VALID_TRANSITIONS = {
    "draft": ["prepared", "withdrawn"],
    "prepared": ["applied", "withdrawn"],
    "applied": ["acknowledged", "interviewing", "rejected", "withdrawn", "ghosted"],
    "acknowledged": ["interviewing", "rejected", "withdrawn", "ghosted"],
    "interviewing": ["offer", "rejected", "withdrawn", "ghosted"],
    "offer": ["withdrawn", "rejected"], # they can withdraw or reject the offer
    "rejected": [],
    "withdrawn": [],
    "ghosted": []
}

class ApplicationService:
    def __init__(self, event_service: EventService | None = None):
        self._events = event_service or EventService()

    async def get_or_create_application(self, job_id: str) -> Application:
        """Get an existing application for a job, or create a new 'draft' one."""
        async with get_session() as session:
            stmt = select(Application).filter_by(job_id=job_id)
            app = (await session.execute(stmt)).scalar_one_or_none()
            if not app:
                app = Application(job_id=job_id, status="draft")
                session.add(app)
                await session.commit()
            return app

    async def update_status(self, application_id: str, new_status: str) -> Application:
        """
        Transition application status.
        Raises ValueError on invalid transition.
        """
        if new_status not in VALID_TRANSITIONS:
            raise ValueError(f"Unknown status: {new_status}")

        async with get_session() as session:
            stmt = select(Application).filter_by(id=application_id)
            app = (await session.execute(stmt)).scalar_one_or_none()
            
            if not app:
                raise ValueError(f"Application {application_id} not found.")

            current_status = app.status

            if new_status not in VALID_TRANSITIONS.get(current_status, []):
                raise ValueError(f"Invalid transition from '{current_status}' to '{new_status}'.")

            app.status = new_status
            await session.commit()

            # Audit event
            await self._events.emit(
                EventType.APPLICATION_STATUS_CHANGED,
                entity_type="application",
                entity_id=app.id,
                payload={
                    "from_status": current_status,
                    "to_status": new_status,
                    "job_id": app.job_id
                }
            )

            return app
