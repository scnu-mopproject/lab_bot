"""师生预约路由。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.booking import Booking
from app.models.room import Room
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingOut
from app.services.booking_service import create_booking

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


def _to_out(db: Session, b: Booking) -> BookingOut:
    out = BookingOut.model_validate(b)
    room = db.get(Room, b.room_id)
    user = db.get(User, b.user_id)
    out.room_name = room.name if room else None
    out.user_name = user.name if user else None
    return out


@router.post("", response_model=BookingOut)
def create(body: BookingCreate, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    room = db.get(Room, body.room_id)
    if not room or not room.is_active:
        raise HTTPException(404, "实验室不存在或已停用")
    try:
        booking = create_booking(
            db, room_id=body.room_id, user_id=user.id,
            start=body.start_time, end=body.end_time, purpose=body.purpose,
        )
    except ValueError as e:
        raise HTTPException(409, str(e))
    return _to_out(db, booking)


@router.get("/mine", response_model=list[BookingOut])
def my_bookings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # 仅展示本人的个人预约；课表占用(source=course)不属于"我的预约"
    stmt = (select(Booking)
            .where(Booking.user_id == user.id, Booking.source == "user")
            .order_by(Booking.start_time.desc()))
    return [_to_out(db, b) for b in db.scalars(stmt).all()]


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel(booking_id: int, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    booking = db.get(Booking, booking_id)
    if not booking or booking.user_id != user.id:
        raise HTTPException(404, "预约不存在")
    if booking.status in ("cancelled", "rejected"):
        raise HTTPException(400, "该预约无需取消")
    booking.status = "cancelled"
    db.commit()
    db.refresh(booking)
    return _to_out(db, booking)
