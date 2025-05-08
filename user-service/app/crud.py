from datetime import datetime
import json

from app.models import User, ProcessedMessage
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
