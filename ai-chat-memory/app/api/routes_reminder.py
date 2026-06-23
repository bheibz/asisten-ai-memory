from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.db.postgres import PostgresDB, get_session

router = APIRouter(prefix="/api/v1", tags=["reminders"])


class ReminderCreate(BaseModel):
    user_id: str
    message: str
    remind_at: str


@router.post("/reminders")
async def create_reminder(body: ReminderCreate, db: PostgresDB = Depends(get_session)):
    from datetime import datetime
    remind_at = datetime.fromisoformat(body.remind_at)
    r = await db.create_reminder(body.user_id, body.message, remind_at)
    return {"id": r.id, "message": r.message, "remind_at": r.remind_at.isoformat()}


@router.get("/reminders/{user_id}")
async def get_reminders(user_id: str, db: PostgresDB = Depends(get_session)):
    reminders = await db.get_reminders_today(user_id)
    return [
        {"id": r.id, "message": r.message, "remind_at": r.remind_at.isoformat()}
        for r in reminders
    ]


@router.put("/reminders/{reminder_id}/shown")
async def mark_shown(reminder_id: str, db: PostgresDB = Depends(get_session)):
    await db.mark_reminder_shown(reminder_id)
    return {"status": "ok"}


@router.delete("/reminders/{reminder_id}")
async def delete_reminder(reminder_id: str, db: PostgresDB = Depends(get_session)):
    await db.delete_reminder(reminder_id)
    return {"status": "deleted"}


@router.post("/messages/{msg_id}/vote")
async def vote_message(msg_id: str, body: dict, db: PostgresDB = Depends(get_session)):
    vote = body.get("vote", "up")
    await db.vote_message(msg_id, vote)
    return {"status": "voted"}
