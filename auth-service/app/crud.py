from app.models import AuthUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List

class UserCreate(BaseModel):
    username: str
    user_id: Optional[str]
    
async def create_user(db: AsyncSession, user_in: UserCreate) -> AuthUser:
    db_user = AuthUser(
        username=user_in.username,
        user_id=user_in.user_id
    ) 
    db.add(db_user)
    await db.flush()
    return db_user

async def get_user(db: AsyncSession) -> List[AuthUser]:
    result = await db.execute(select(AuthUser))
    return result.scalars().all()