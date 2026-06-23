from fastapi import APIRouter, Depends

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
        return {"error": "User not found"}, 404
    return {"id": str(user.id), "username": user.username, "profile": user.ai_profile}
