from datetime import datetime

from pydantic import BaseModel


class RepairCreate(BaseModel):
    room_id: int
    device_name: str
    description: str
    images: list[str] = []


class RepairOut(BaseModel):
    id: int
    room_id: int
    device_name: str
    description: str
    images: list[str]
    reporter_id: int
    handler_id: int | None = None
    status: str
    logs: list
    created_at: datetime
    updated_at: datetime
    room_name: str | None = None
    reporter_name: str | None = None

    model_config = {"from_attributes": True}


class RepairTransition(BaseModel):
    status: str  # assigned / in_progress / done / closed
    note: str | None = None
    handler_id: int | None = None
