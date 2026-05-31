from datetime import datetime

from pydantic import BaseModel


class BookingCreate(BaseModel):
    room_id: int
    start_time: datetime
    end_time: datetime
    purpose: str | None = None


class BookingOut(BaseModel):
    id: int
    room_id: int
    user_id: int
    start_time: datetime
    end_time: datetime
    purpose: str | None = None
    status: str
    source: str
    course_name: str | None = None
    created_at: datetime
    room_name: str | None = None
    user_name: str | None = None

    model_config = {"from_attributes": True}


class BookingReview(BaseModel):
    approve: bool
    reason: str | None = None
