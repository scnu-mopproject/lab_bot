"""场地管理：影响预检、停用（取消/迁移联动）、受限物理删除。"""
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.repair import Repair
from app.models.room import Room
from app.services.booking_service import future_active_bookings, overlapping_bookings

OPEN_REPAIR_STATUSES = ("submitted", "assigned", "in_progress")


def _open_repairs(db: Session, room_id: int) -> int:
    return db.scalar(
        select(func.count()).select_from(Repair).where(
            Repair.room_id == room_id, Repair.status.in_(OPEN_REPAIR_STATUSES)
        )
    ) or 0


def room_impact(db: Session, room_id: int) -> dict:
    """停用前预检：未来预约（区分师生/课表）与未完成报修数量；以及全部历史记录数。"""
    futures = future_active_bookings(db, room_id)
    user_bookings = [b for b in futures if b.source == "user"]
    course_bookings = [b for b in futures if b.source == "course"]
    total_bookings = db.scalar(
        select(func.count()).select_from(Booking).where(Booking.room_id == room_id)) or 0
    total_repairs = db.scalar(
        select(func.count()).select_from(Repair).where(Repair.room_id == room_id)) or 0
    return {
        "future_bookings": len(futures),
        "user_bookings": len(user_bookings),
        "course_bookings": len(course_bookings),
        "open_repairs": _open_repairs(db, room_id),
        "total_bookings": total_bookings,
        "total_repairs": total_repairs,
    }


def list_rooms_with_counts(db: Session) -> list[dict]:
    rooms = list(db.scalars(select(Room).order_by(Room.is_active.desc(), Room.id)).all())
    out = []
    for r in rooms:
        futures = future_active_bookings(db, r.id)
        out.append({
            "id": r.id, "name": r.name, "location": r.location, "capacity": r.capacity,
            "description": r.description, "open_time": r.open_time, "close_time": r.close_time,
            "is_active": r.is_active,
            "future_bookings": len(futures),
            "open_repairs": _open_repairs(db, r.id),
        })
    return out


def disable_room(db: Session, room: Room, *, action: str, target_room_id: int | None,
                 reason: str | None) -> dict:
    """停用场地并联动处理未来预约。

    action="cancel"：未来有效预约（含课表）全部取消，记 system_note。
    action="relocate"：师生预约尝试迁到 target_room_id（冲突的列出交管理员）；
                       课表占用一律取消（需重导课表）。
    """
    futures = future_active_bookings(db, room.id)
    cancelled = relocated = course_cancelled = 0
    conflicts: list[Booking] = []
    cancel_reason = reason or f"因场地「{room.name}」停用，预约已取消"

    target = db.get(Room, target_room_id) if (action == "relocate" and target_room_id) else None
    if action == "relocate" and not target:
        raise ValueError("迁移目标场地不存在")

    for b in futures:
        if b.source == "course":
            # 课表占用一律取消（停用后需在新场地重导课表）
            b.status = "cancelled"
            b.system_note = f"因场地「{room.name}」停用，课表占用已清除，请重新导入课表"
            course_cancelled += 1
            continue
        if action == "cancel":
            b.status = "cancelled"
            b.system_note = cancel_reason
            cancelled += 1
        else:  # relocate
            if overlapping_bookings(db, target.id, b.start_time, b.end_time, exclude_id=b.id):
                conflicts.append(b)  # 冲突：留待管理员逐条处理
            else:
                b.room_id = target.id
                b.system_note = f"因场地「{room.name}」停用，已为你改约至「{target.name}」，时间不变"
                relocated += 1

    room.is_active = False
    db.commit()
    return {
        "cancelled": cancelled,
        "relocated": relocated,
        "course_cancelled": course_cancelled,
        "conflicts": conflicts,
        "target_room": target,
    }


def can_hard_delete(db: Session, room_id: int) -> bool:
    """无任何关联预约/报修时才允许物理删除。"""
    has_booking = db.scalar(select(Booking.id).where(Booking.room_id == room_id).limit(1))
    has_repair = db.scalar(select(Repair.id).where(Repair.room_id == room_id).limit(1))
    return has_booking is None and has_repair is None


def hard_delete_room(db: Session, room: Room, *, cascade: bool = False) -> None:
    if cascade:  # 强制删除：连同该场地的历史预约/报修一并清除
        db.execute(delete(Booking).where(Booking.room_id == room.id))
        db.execute(delete(Repair).where(Repair.room_id == room.id))
    db.delete(room)
    db.commit()
