from datetime import datetime
import json

from app.models import AuthUser, ProcessedMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uuid

class UserCreate(BaseModel):
    username: str

class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    user_id: Optional[uuid.UUID] = None
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

# 処理済みメッセージに関する操作 #

async def check_message_processed(db: AsyncSession, message_id: uuid.UUID, source_queue: str) -> Optional[ProcessedMessage]:
    """
    メッセージが既に処理済みかどうかをチェックする
    
    Args:
        db: データベースセッション
        message_id: メッセージID
        source_queue: ソースキュー名
        
    Returns:
        既に処理済みの場合はProcessedMessageオブジェクト、そうでなければNone
    """
    result = await db.execute(
        select(ProcessedMessage).where(
            ProcessedMessage.message_id == message_id,
            ProcessedMessage.source_queue == source_queue
        )
    )
    return result.scalars().first()

async def save_processed_message(
    db: AsyncSession, 
    message_id: uuid.UUID, 
    source_queue: str, 
    status: str,
    result_data: Optional[Dict[str, Any]] = None
) -> ProcessedMessage:
    """
    処理済みメッセージを保存する
    
    Args:
        db: データベースセッション
        message_id: メッセージID
        source_queue: ソースキュー名
        status: 処理ステータス
        result_data: 処理結果データ（オプション）
        
    Returns:
        保存されたProcessedMessageオブジェクト
    """
    # 結果データがある場合はJSON文字列に変換
    result_data_str = json.dumps(result_data) if result_data else None
    
    processed_msg = ProcessedMessage(
        message_id=message_id,
        source_queue=source_queue,
        status=status,
        result_data=result_data_str
    )
    
    db.add(processed_msg)
    await db.flush()
    return processed_msg
