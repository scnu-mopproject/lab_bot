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


class RoomUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    capacity: int | None = None
    description: str | None = None
    open_time: str | None = None
    close_time: str | None = None


class RoomAdminOut(RoomOut):
    """管理端场地：附带影响数量。"""
    future_bookings: int = 0
    open_repairs: int = 0


class RoomImpact(BaseModel):
    future_bookings: int
    user_bookings: int
    course_bookings: int
    open_repairs: int
    total_bookings: int = 0   # 全部历史预约数（含已取消）
    total_repairs: int = 0    # 全部报修数（含已完成）


class RoomDisableRequest(BaseModel):
    action: str = "cancel"            # cancel | relocate
    target_room_id: int | None = None  # action=relocate 时必填
    reason: str | None = None


class BookingBrief(BaseModel):
    id: int
    start_time: datetime
    end_time: datetime
    user_name: str | None = None
    purpose: str | None = None


class RoomDisableResult(BaseModel):
    cancelled: int
    relocated: int
    course_cancelled: int
    target_room_id: int | None = None
    target_room_name: str | None = None
    conflicts: list[BookingBrief] = []


class BookingRelocate(BaseModel):
    room_id: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    note: str | None = None


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
