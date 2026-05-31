from datetime import datetime

from pydantic import BaseModel


class RoomOut(BaseModel):
    id: int
    name: str
    location: str | None = None
    capacity: int
    description: str | None = None
    open_time: str
    close_time: str
    is_active: bool

    model_config = {"from_attributes": True}


class RoomCreate(BaseModel):
    name: str
    location: str | None = None
    capacity: int = 0
    description: str | None = None
    open_time: str = "08:00"
    close_time: str = "22:00"


class SlotOut(BaseModel):
    """单个时段（半小时粒度）的占用情况。"""
    start: datetime
    end: datetime
    available: bool
    label: str | None = None  # 占用原因，如课程名/已预约


class AvailabilityOut(BaseModel):
    room_id: int
    date: str
    slots: list[SlotOut]
