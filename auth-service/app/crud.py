from datetime import datetime

from app.models import AuthUser
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
    user_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # SQLAlchemyモデルからの変換を可能にする

    
async def create(db: AsyncSession, user_in: UserCreate) -> AuthUser:
    db_user = AuthUser(
        username=user_in.username,
        user_id=None
    ) 
    db.add(db_user)
    await db.flush()
    return UserResponse.model_validate(db_user)

async def get_user(db: AsyncSession) -> List[AuthUser]:
    result = await db.execute(select(AuthUser))
    users = result.scalars().all()
    return [UserResponse.model_validate(user) for user in users]

async def update_user_id(db: AsyncSession, username: str, user_id: uuid.UUID) -> Optional[AuthUser]:
    """ユーザー名に基づいてAuthUserのuser_idを更新する"""
    result = await db.execute(select(AuthUser).where(AuthUser.username == username))
    auth_user = result.scalars().first()
    
    if auth_user:
        auth_user.user_id = user_id
        await db.flush()
        return UserResponse.model_validate(auth_user)
    return None
