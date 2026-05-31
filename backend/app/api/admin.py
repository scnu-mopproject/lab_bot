"""管理员路由：预约审批、报修流转、课表导入、FAQ 维护、实验室管理。"""
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models.booking import Booking
from app.models.faq import FAQ
from app.models.repair import Repair
from app.models.room import Room
from app.models.user import User
from app.schemas.booking import BookingOut, BookingReview
from app.schemas.chat import FAQIn, FAQOut
from app.schemas.repair import RepairOut, RepairTransition
from app.schemas.room import RoomCreate, RoomOut
from app.schemas.schedule import ScheduleImportResult
from app.services import repair_service
from app.services.schedule_import import import_schedule

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


# ---------- 实验室管理 ----------
@router.post("/rooms", response_model=RoomOut)
def create_room(body: RoomCreate, db: Session = Depends(get_db)):
    room = Room(**body.model_dump())
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


# ---------- 预约审批 ----------
@router.get("/bookings", response_model=list[BookingOut])
def list_bookings(status: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Booking).order_by(Booking.start_time.desc())
    if status:
        stmt = stmt.where(Booking.status == status)
    out = []
    for b in db.scalars(stmt).all():
        o = BookingOut.model_validate(b)
        room = db.get(Room, b.room_id)
        user = db.get(User, b.user_id)
        o.room_name = room.name if room else None
        o.user_name = user.name if user else None
        out.append(o)
    return out


@router.post("/bookings/{booking_id}/review", response_model=BookingOut)
def review_booking(booking_id: int, body: BookingReview, db: Session = Depends(get_db)):
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(404, "预约不存在")
    if booking.status != "pending":
        raise HTTPException(400, "该预约不处于待审批状态")
    booking.status = "approved" if body.approve else "rejected"
    db.commit()
    db.refresh(booking)
    out = BookingOut.model_validate(booking)
    room = db.get(Room, booking.room_id)
    out.room_name = room.name if room else None
    return out


# ---------- 报修流转 ----------
@router.get("/repairs", response_model=list[RepairOut])
def list_repairs(status: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Repair).order_by(Repair.created_at.desc())
    if status:
        stmt = stmt.where(Repair.status == status)
    out = []
    for r in db.scalars(stmt).all():
        o = RepairOut.model_validate(r)
        room = db.get(Room, r.room_id)
        reporter = db.get(User, r.reporter_id)
        o.room_name = room.name if room else None
        o.reporter_name = reporter.name if reporter else None
        out.append(o)
    return out


@router.post("/repairs/{repair_id}/transition", response_model=RepairOut)
def transition_repair(repair_id: int, body: RepairTransition,
                      db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    repair = db.get(Repair, repair_id)
    if not repair:
        raise HTTPException(404, "报修单不存在")
    try:
        repair_service.transition(
            repair, new_status=body.status, operator=admin.name,
            note=body.note, handler_id=body.handler_id or admin.id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    db.commit()
    db.refresh(repair)
    o = RepairOut.model_validate(repair)
    room = db.get(Room, repair.room_id)
    o.room_name = room.name if room else None
    return o


# ---------- 课表批量导入 ----------
@router.post("/schedules/import", response_model=ScheduleImportResult)
async def import_schedules(
    file: UploadFile = File(...),
    term_start_monday: str = Form(..., description="学期第一周周一，YYYY-MM-DD"),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    try:
        start_monday = date.fromisoformat(term_start_monday)
    except ValueError:
        raise HTTPException(400, "term_start_monday 格式应为 YYYY-MM-DD")
    content = await file.read()
    try:
        result = import_schedule(
            db, content=content, filename=file.filename or "upload.csv",
            operator_user_id=admin.id, term_start_monday=start_monday,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return result


# ---------- FAQ 知识库 ----------
@router.get("/faqs", response_model=list[FAQOut])
def list_faqs(db: Session = Depends(get_db)):
    return list(db.scalars(select(FAQ)).all())


@router.post("/faqs", response_model=FAQOut)
def create_faq(body: FAQIn, db: Session = Depends(get_db)):
    faq = FAQ(**body.model_dump())
    db.add(faq)
    db.commit()
    db.refresh(faq)
    return faq


@router.put("/faqs/{faq_id}", response_model=FAQOut)
def update_faq(faq_id: int, body: FAQIn, db: Session = Depends(get_db)):
    faq = db.get(FAQ, faq_id)
    if not faq:
        raise HTTPException(404, "FAQ 不存在")
    for k, v in body.model_dump().items():
        setattr(faq, k, v)
    db.commit()
    db.refresh(faq)
    return faq


@router.delete("/faqs/{faq_id}")
def delete_faq(faq_id: int, db: Session = Depends(get_db)):
    faq = db.get(FAQ, faq_id)
    if not faq:
        raise HTTPException(404, "FAQ 不存在")
    db.delete(faq)
    db.commit()
    return {"ok": True}
