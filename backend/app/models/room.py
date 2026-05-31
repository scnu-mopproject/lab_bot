from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    open_time: Mapped[str] = mapped_column(String(5), default="08:00")  # HH:MM
    close_time: Mapped[str] = mapped_column(String(5), default="22:00")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
