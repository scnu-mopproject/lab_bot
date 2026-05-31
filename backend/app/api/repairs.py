"""报修路由（共享表格式）。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.repair import Repair
from app.models.room import Room
from app.models.user import User
from app.schemas.repair import RepairCreate, RepairOut

router = APIRouter(prefix="/api/repairs", tags=["repairs"])


def _to_out(db: Session, r: Repair) -> RepairOut:
    out = RepairOut.model_validate(r)
    room = db.get(Room, r.room_id)
    reporter = db.get(User, r.reporter_id)
    out.room_name = room.name if room else None
    out.reporter_name = reporter.name if reporter else None
    return out


@router.post("", response_model=RepairOut)
def create(body: RepairCreate, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    if not db.get(Room, body.room_id):
        raise HTTPException(404, "实验室不存在")
    repair = Repair(
        room_id=body.room_id, device_name=body.device_name, description=body.description,
        images=body.images, reporter_id=user.id, status="submitted",
        logs=[{"status": "submitted", "operator": user.name, "note": "用户提交报修"}],
    )
    db.add(repair)
    db.commit()
    db.refresh(repair)
    return _to_out(db, repair)


@router.get("", response_model=list[RepairOut])
def list_repairs(scope: str = Query("mine", pattern="^(mine|all)$"),
                 status: str | None = None,
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """scope=mine 看自己的；scope=all 仅管理员可看全部。"""
    stmt = select(Repair).order_by(Repair.created_at.desc())
    if scope == "all":
        if user.role != "admin":
            raise HTTPException(403, "需要管理员权限")
    else:
        stmt = stmt.where(Repair.reporter_id == user.id)
    if status:
        stmt = stmt.where(Repair.status == status)
    return [_to_out(db, r) for r in db.scalars(stmt).all()]


@router.get("/{repair_id}", response_model=RepairOut)
def get_repair(repair_id: int, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    repair = db.get(Repair, repair_id)
    if not repair:
        raise HTTPException(404, "报修单不存在")
    if user.role != "admin" and repair.reporter_id != user.id:
        raise HTTPException(403, "无权查看")
    return _to_out(db, repair)
