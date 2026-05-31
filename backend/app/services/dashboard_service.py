"""管理员看板统计。"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.chat_log import ChatLog
from app.models.repair import Repair
from app.models.room import Room
from app.models.user import User

REPAIR_OPEN = ("submitted", "assigned", "in_progress")


def _naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def build_dashboard(db: Session, *, top_n: int = 8, hot_days: int = 30) -> dict:
    now = _naive_now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ahead = now + timedelta(days=7)

    # ---- 汇总数字 ----
    pending_booking_cnt = db.scalar(
        select(func.count()).select_from(Booking).where(Booking.status == "pending")
    ) or 0
    open_repair_cnt = db.scalar(
        select(func.count()).select_from(Repair).where(Repair.status.in_(REPAIR_OPEN))
    ) or 0
    today_booking_cnt = db.scalar(
        select(func.count()).select_from(Booking).where(
            Booking.start_time >= today_start,
            Booking.start_time < today_start + timedelta(days=1),
            Booking.status.in_(("pending", "approved")),
        )
    ) or 0
    room_cnt = db.scalar(select(func.count()).select_from(Room).where(Room.is_active == True)) or 0  # noqa: E712

    # ---- 待审批预约（取最近若干条） ----
    pend_rows = db.scalars(
        select(Booking).where(Booking.status == "pending").order_by(Booking.start_time).limit(top_n)
    ).all()
    pending_bookings = []
    for b in pend_rows:
        room = db.get(Room, b.room_id)
        u = db.get(User, b.user_id)
        pending_bookings.append({
            "id": b.id,
            "room_name": room.name if room else None,
            "user_name": u.name if u else None,
            "start_time": b.start_time,
            "end_time": b.end_time,
            "purpose": b.purpose,
        })

    # ---- 待维修设备 ----
    repair_status_rows = db.execute(
        select(Repair.status, func.count()).group_by(Repair.status)
    ).all()
    repair_status = {s: c for s, c in repair_status_rows}
    open_rows = db.scalars(
        select(Repair).where(Repair.status.in_(REPAIR_OPEN)).order_by(Repair.created_at.desc()).limit(top_n)
    ).all()
    pending_repairs = []
    for r in open_rows:
        room = db.get(Room, r.room_id)
        pending_repairs.append({
            "id": r.id,
            "device_name": r.device_name,
            "room_name": room.name if room else None,
            "status": r.status,
            "created_at": r.created_at,
        })

    # ---- 高频咨询问题（近 hot_days 天，按命中 FAQ 聚合；未命中按原文聚合） ----
    since = now - timedelta(days=hot_days)
    label = func.coalesce(ChatLog.matched_question, ChatLog.message)
    hot_rows = db.execute(
        select(label, func.count().label("c"))
        .where(ChatLog.created_at >= since)
        .group_by(label)
        .order_by(func.count().desc())
        .limit(top_n)
    ).all()
    hot_questions = [{"question": q, "count": c} for q, c in hot_rows]

    # ---- 实验室使用率 Top（已批准/课表占用时段数，近 hot_days） ----
    usage_rows = db.execute(
        select(Booking.room_id, func.count().label("c"))
        .where(Booking.status.in_(("approved", "pending")), Booking.start_time >= since)
        .group_by(Booking.room_id)
        .order_by(func.count().desc())
        .limit(5)
    ).all()
    room_usage = []
    for rid, c in usage_rows:
        room = db.get(Room, rid)
        room_usage.append({"room_name": room.name if room else f"#{rid}", "count": c})

    return {
        "summary": {
            "pending_bookings": pending_booking_cnt,
            "open_repairs": open_repair_cnt,
            "today_bookings": today_booking_cnt,
            "active_rooms": room_cnt,
        },
        "pending_bookings": pending_bookings,
        "repair_status": repair_status,
        "pending_repairs": pending_repairs,
        "hot_questions": hot_questions,
        "room_usage": room_usage,
        "generated_at": now,
    }
