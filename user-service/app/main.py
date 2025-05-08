from fastapi import FastAPI, Request, Depends, HTTPException, status
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from app.db import Database
from app.session import get_async_session
from app.crud import UserCreate, create, get_user
import asyncio

from app.core.rabbitmq import rabbitmq_client
from app.messaging.user_handlers import register_message_handlers
from app.core.logging import get_logger

logger = get_logger(__name__)


app = FastAPI()

@app.on_event("startup")
async def startup_db_client():
    # データベース初期化
    db = Database()
    await db.init()
    print("Database initialized on startup")
    
    # RabbitMQ接続の初期化
    try:
        await rabbitmq_client.connect()
        
        # メッセージハンドラーの登録
        await register_message_handlers()
        
        # メッセージ消費の開始
        await rabbitmq_client.start_consuming()
        
        logger.info("RabbitMQコンシューマーを初期化しました")
    except Exception as e:
        logger.error(f"RabbitMQ初期化中にエラーが発生しました: {str(e)}")

@app.post("/create_user")
async def create_user(
    request: Request,
    user_in: UserCreate,
    async_session: AsyncSession = Depends(get_async_session)
) -> Any:
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

@app.on_event("shutdown")
async def shutdown_event():
    # RabbitMQ接続のクローズ
    try:
        await rabbitmq_client.close()
        logger.info("RabbitMQコネクションを正常に終了しました")
    except Exception as e:
        logger.error(f"RabbitMQ終了中にエラーが発生しました: {str(e)}")

async def main() -> None:
    db = Database()
    await db.init()
    print("Database initialized")

if __name__ == "__main__":
    import uvicorn
    asyncio.run(main())
    uvicorn.run(app, host="0.0.0.0", port=8081)
