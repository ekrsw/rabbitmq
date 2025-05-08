from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
import uuid

from sqlalchemy import DateTime, String, Uuid, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, index=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo("Asia/Tokyo"))
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo("Asia/Tokyo")),
        onupdate=lambda: datetime.now(ZoneInfo("Asia/Tokyo"))
    )

class AuthUser(Base):
    __tablename__ = "auth_users"

    username: Mapped[str] = mapped_column(String, nullable=False, index=True, unique=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True, index=True, unique=True)

class ProcessedMessage(Base):
    """処理済みメッセージを追跡するためのテーブル（冪等性の確保）"""
    __tablename__ = "processed_messages"
    
    message_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True, unique=True)
    source_queue: Mapped[str] = mapped_column(String, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo("Asia/Tokyo"))
    )
    status: Mapped[str] = mapped_column(String, nullable=False)
    result_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
