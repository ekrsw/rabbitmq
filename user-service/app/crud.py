from datetime import datetime

from app.models import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List
import uuid

class UserCreate(BaseModel):
    username: str

class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # SQLAlchemyモデルからの変換を可能にする

    
async def create(db: AsyncSession, user_in: UserCreate) -> User:
    db_user = User(
        username=user_in.username,
    ) 
    db.add(db_user)
    await db.flush()
    return UserResponse.model_validate(db_user)

async def get_user(db: AsyncSession) -> List[User]:
    result = await db.execute(select(User))
    users = result.scalars().all()
    return [UserResponse.model_validate(user) for user in users]