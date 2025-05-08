from fastapi import FastAPI, Request, Depends, HTTPException, status
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from app.db import Database
from app.session import get_async_session
from app.crud import UserCreate, create, get_user
import asyncio

from app.core.rabbitmq import rabbitmq_client, USER_CREATE_QUEUE
from app.schemas.message import UserCreateRequest

from app.core.logging import get_logger

logger = get_logger(__name__)


app = FastAPI()

@app.on_event("startup")
async def startup_db_client():
    db = Database()
    await db.init()
    print("Database initialized on startup")

@app.post("/create_user")
async def create_user(
    request: Request,
    user_in: UserCreate,
    async_session: AsyncSession = Depends(get_async_session)
) -> Any:
    # 2. user-serviceにユーザー作成リクエストを送信
    user_create_request = UserCreateRequest(
        username=user_in.username,
    )
    
    # メッセージをパブリッシュ
    success = await rabbitmq_client.publish_message(
        USER_CREATE_QUEUE,
        user_create_request.model_dump()
    )
    
    if success:
        logger.info(f"user-serviceにユーザー作成リクエストを送信しました: {user_create_request.message_id}")
    else:
        logger.error(f"user-serviceへのメッセージ送信に失敗しました: {user_in.username}")
        # メッセージ送信に失敗した場合でもユーザー作成は成功しているので、エラーにはしない
        
    user = await create(async_session, user_in)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User creation failed"
        )
    return user


@app.get("/get_users")
async def get_users(
    request: Request,
    async_session: AsyncSession = Depends(get_async_session)
) -> Any:
    users = await get_user(async_session)
    if not users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No users found"
        )
    return users

async def main() -> None:
    db = Database()
    await db.init()
    print("Database initialized")

if __name__ == "__main__":
    import uvicorn
    asyncio.run(main())
    uvicorn.run(app, host="0.0.0.0", port=8080)