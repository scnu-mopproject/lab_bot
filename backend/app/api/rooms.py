"""实验室与时段可用性路由。"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.room import Room
from app.models.user import User
from app.schemas.room import AvailabilityOut, RoomOut
from app.services.booking_service import get_availability

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


@router.get("", response_model=list[RoomOut])
def list_rooms(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return list(db.scalars(select(Room).where(Room.is_active == True)).all())  # noqa: E712


@router.get("/{room_id}", response_model=RoomOut)
def get_room(room_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(404, "实验室不存在")
    return room


@router.get("/{room_id}/availability", response_model=AvailabilityOut)
def availability(room_id: int, date_: str = Query(alias="date"),
                 db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(404, "实验室不存在")
    try:
        day = date.fromisoformat(date_)
    except ValueError:
        raise HTTPException(400, "日期格式应为 YYYY-MM-DD")
    slots = get_availability(db, room, day)
    return {"room_id": room_id, "date": date_, "slots": slots}
