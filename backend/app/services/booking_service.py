"""预约核心逻辑：时段生成、冲突检测、创建。"""
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.booking import Booking
from app.models.room import Room

SLOT_MINUTES = 30
ACTIVE_STATUSES = ("pending", "approved")  # 占用时段的预约状态


def to_naive_utc(dt: datetime) -> datetime:
    """统一为 naive UTC，规避 SQLite 不保存时区导致的比较错误。"""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def overlapping_bookings(db: Session, room_id: int, start: datetime, end: datetime,
                         exclude_id: int | None = None) -> list[Booking]:
    """返回与 [start, end) 时间段重叠且占用中的预约。"""
    start, end = to_naive_utc(start), to_naive_utc(end)
    stmt = select(Booking).where(
        Booking.room_id == room_id,
        Booking.status.in_(ACTIVE_STATUSES),
        and_(Booking.start_time < end, Booking.end_time > start),
    )
    if exclude_id is not None:
        stmt = stmt.where(Booking.id != exclude_id)
    return list(db.scalars(stmt).all())


def get_availability(db: Session, room: Room, day: date) -> list[dict]:
    """生成某天按 30 分钟粒度的时段占用情况。"""
    open_t = _parse_hhmm(room.open_time)
    close_t = _parse_hhmm(room.close_time)
    day_start = datetime.combine(day, open_t)
    day_end = datetime.combine(day, close_t)

    bookings = overlapping_bookings(db, room.id, day_start, day_end)

    slots = []
    cursor = day_start
    while cursor < day_end:
        nxt = cursor + timedelta(minutes=SLOT_MINUTES)
        label = None
        available = True
        for b in bookings:
            if b.start_time < nxt and b.end_time > cursor:
                available = False
                label = b.course_name or ("已预约" if b.source == "user" else "占用")
                break
        slots.append({"start": cursor, "end": nxt, "available": available, "label": label})
        cursor = nxt
    return slots


def now_naive() -> datetime:
    """当前时间的 naive UTC（与库内存储一致）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def future_active_bookings(db: Session, room_id: int) -> list[Booking]:
    """某场地未来仍有效（pending/approved 且未结束）的预约。"""
    now = now_naive()
    stmt = select(Booking).where(
        Booking.room_id == room_id,
        Booking.status.in_(ACTIVE_STATUSES),
        Booking.end_time > now,
    ).order_by(Booking.start_time)
    return list(db.scalars(stmt).all())


def relocate_booking(db: Session, booking: Booking, *, target_room_id: int,
                     start: datetime | None = None, end: datetime | None = None,
                     note: str | None = None, commit: bool = True) -> Booking:
    """改约：换场地（可同时换时间），带冲突校验。冲突时抛 ValueError。"""
    new_start = to_naive_utc(start) if start else booking.start_time
    new_end = to_naive_utc(end) if end else booking.end_time
    if new_end <= new_start:
        raise ValueError("结束时间必须晚于开始时间")
    if overlapping_bookings(db, target_room_id, new_start, new_end, exclude_id=booking.id):
        raise ValueError("目标场地该时段已被占用")
    booking.room_id = target_room_id
    booking.start_time = new_start
    booking.end_time = new_end
    if note is not None:
        booking.system_note = note
    if commit:
        db.commit()
        db.refresh(booking)
    return booking


def create_booking(db: Session, *, room_id: int, user_id: int, start: datetime, end: datetime,
                   purpose: str | None, source: str = "user", course_name: str | None = None,
                   commit: bool = True) -> Booking:
    start, end = to_naive_utc(start), to_naive_utc(end)
    if end <= start:
        raise ValueError("结束时间必须晚于开始时间")
    conflicts = overlapping_bookings(db, room_id, start, end)
    if conflicts:
        raise ValueError("该时段已被占用，请重新选择")

    status = "approved" if (settings.booking_auto_approve or source == "course") else "pending"
    booking = Booking(
        room_id=room_id, user_id=user_id, start_time=start, end_time=end,
        purpose=purpose, status=status, source=source, course_name=course_name,
    )
    db.add(booking)
    if commit:
        db.commit()
        db.refresh(booking)
    return booking
