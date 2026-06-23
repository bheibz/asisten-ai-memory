from fastapi import APIRouter, Depends, HTTPException

from app.db.postgres import PostgresDB, get_session

router = APIRouter(prefix="/api/v1", tags=["users"])


@router.post("/users")
async def create_user(username: str, email: str = None, db: PostgresDB = Depends(get_session)):
    user = await db.get_or_create_user(username, email)
    return {"id": str(user.id), "username": user.username}


@router.get("/users/{user_id}")
async def get_user(user_id: str, db: PostgresDB = Depends(get_session)):
    user = await db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": str(user.id), "username": user.username, "profile": user.user_profile, "preferred_ai_name": user.preferred_ai_name}
