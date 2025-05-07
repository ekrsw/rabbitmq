from fastapi import FastAPI, Request, Depends, HTTPException, status
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from app.db import Database
from app.session import get_async_session
from app.crud import UserCreate, create, get_user
import asyncio


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
    uvicorn.run(app, host="0.0.0.0", port=8081)