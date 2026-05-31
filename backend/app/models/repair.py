from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Repair(Base):
    __tablename__ = "repairs"

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True)
    device_name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(1024))
    images: Mapped[list] = mapped_column(JSON, default=list)  # 图片 URL 列表
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    handler_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # 状态: submitted / assigned / in_progress / done / closed
    status: Mapped[str] = mapped_column(String(16), default="submitted", index=True)
    # 流转日志: [{time, status, operator, note}]
    logs: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
