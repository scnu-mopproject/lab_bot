from datetime import datetime

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    pending_bookings: int
    open_repairs: int
    today_bookings: int
    active_rooms: int


class PendingBooking(BaseModel):
    id: int
    room_name: str | None = None
    user_name: str | None = None
    start_time: datetime
    end_time: datetime
    purpose: str | None = None


class PendingRepair(BaseModel):
    id: int
    device_name: str
    room_name: str | None = None
    status: str
    created_at: datetime


class HotQuestion(BaseModel):
    question: str
    count: int


class RoomUsage(BaseModel):
    room_name: str
    count: int


class DashboardOut(BaseModel):
    summary: DashboardSummary
    pending_bookings: list[PendingBooking]
    repair_status: dict[str, int]
    pending_repairs: list[PendingRepair]
    hot_questions: list[HotQuestion]
    room_usage: list[RoomUsage]
    generated_at: datetime
