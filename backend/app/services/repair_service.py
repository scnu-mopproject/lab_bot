"""报修状态流转。"""
from datetime import datetime, timezone

from app.models.repair import Repair

# 允许的状态流转
TRANSITIONS = {
    "submitted": {"assigned", "closed"},
    "assigned": {"in_progress", "closed"},
    "in_progress": {"done", "closed"},
    "done": {"closed", "in_progress"},
    "closed": set(),
}


def transition(repair: Repair, *, new_status: str, operator: str,
               note: str | None = None, handler_id: int | None = None) -> Repair:
    allowed = TRANSITIONS.get(repair.status, set())
    if new_status not in allowed:
        raise ValueError(f"不允许从 {repair.status} 流转到 {new_status}")

    repair.status = new_status
    if handler_id is not None:
        repair.handler_id = handler_id
    # JSON 列需重新赋值以触发 ORM 脏检测
    logs = list(repair.logs or [])
    logs.append({
        "time": datetime.now(timezone.utc).isoformat(),
        "status": new_status,
        "operator": operator,
        "note": note,
    })
    repair.logs = logs
    return repair
