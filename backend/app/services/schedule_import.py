"""课表批量导入：把课表行展开为多条 course 预约。

支持 CSV / Excel(xlsx)，列（含表头，顺序固定或按列名）：
    room_name, weekday, start_period, end_period, start_week, end_week, course_name
- weekday: 1-7（周一到周日）
- start_period/end_period: 节次，映射到具体时间（PERIOD_TIMES）
- start_week/end_week: 起止教学周
导入时以 `term_start_monday`（学期第一周周一）为基准计算实际日期。
"""
import csv
import io
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.room import Room
from app.services.booking_service import create_booking

# 节次 -> (开始, 结束) 时间，按需调整为学校实际作息
PERIOD_TIMES: dict[int, tuple[time, time]] = {
    1: (time(8, 0), time(8, 45)),
    2: (time(8, 55), time(9, 40)),
    3: (time(10, 0), time(10, 45)),
    4: (time(10, 55), time(11, 40)),
    5: (time(14, 0), time(14, 45)),
    6: (time(14, 55), time(15, 40)),
    7: (time(16, 0), time(16, 45)),
    8: (time(16, 55), time(17, 40)),
    9: (time(19, 0), time(19, 45)),
    10: (time(19, 55), time(20, 40)),
    11: (time(20, 50), time(21, 35)),
}


def build_schedule_template() -> bytes:
    """生成课表导入 Excel 模板：示例数据 + 填写说明 + 节次对照。"""
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "课表模板"
    headers = ["room_name", "weekday", "start_period", "end_period",
               "start_week", "end_week", "course_name"]
    ws.append(headers)
    for row in [
        ["计算机实验室 A301", 1, 1, 2, 1, 16, "程序设计基础"],
        ["计算机实验室 A301", 3, 5, 6, 1, 16, "数据结构"],
        ["人工智能实验室 B205", 2, 3, 4, 1, 8, "机器学习"],
    ]:
        ws.append(row)
    for i, w in enumerate([22, 9, 13, 12, 11, 10, 18], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws2 = wb.create_sheet("填写说明")
    for r in [
        ["列名", "说明"],
        ["room_name", "实验室名称，必须与系统中的实验室名称完全一致"],
        ["weekday", "星期：1=周一，2=周二 … 7=周日"],
        ["start_period / end_period", "起止节次（见下方节次对照），如 1 到 2"],
        ["start_week / end_week", "起止教学周，如第 1 周到第 16 周"],
        ["course_name", "课程名称（选填，留空记为“课程占用”）"],
        ["", ""],
        ["节次", "时间"],
    ]:
        ws2.append(r)
    for p, (s, e) in PERIOD_TIMES.items():
        ws2.append([f"第{p}节", f"{s.strftime('%H:%M')}-{e.strftime('%H:%M')}"])
    ws2.column_dimensions["A"].width = 26
    ws2.column_dimensions["B"].width = 44

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _read_rows(content: bytes, filename: str) -> list[dict]:
    name = filename.lower()
    if name.endswith(".csv"):
        text = content.decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(text)))
    if name.endswith(".xlsx"):
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(content), read_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        header = [str(h).strip() if h is not None else "" for h in rows[0]]
        return [dict(zip(header, r)) for r in rows[1:] if any(c is not None for c in r)]
    raise ValueError("仅支持 .csv 或 .xlsx 文件")


def import_schedule(db: Session, *, content: bytes, filename: str, operator_user_id: int,
                    term_start_monday: date, mode: str = "replace") -> dict:
    """解析课表并生成 course 预约。返回 {created, skipped, removed, conflicts}。

    mode="replace"（覆盖，默认）：先清空上一次的课表占用（source="course"）再写入，
        实现"以最新一次导入为准"，清空后 conflicts 仅为与师生预约的真实重叠。
    mode="append"（追加）：不清空，仅新增；冲突检测会跳过已被占用（课表或师生预约）的
        时段并记入 conflicts，从而天然防止重复与撞课。
    """
    rows = _read_rows(content, filename)  # 文件非法在此先报错，不会误删
    removed = 0
    if mode == "replace":
        removed = db.execute(delete(Booking).where(Booking.source == "course")).rowcount or 0
    room_cache: dict[str, Room | None] = {}
    created = skipped = 0
    conflicts: list[str] = []

    for idx, row in enumerate(rows, start=2):  # 2 = 含表头后的首数据行
        try:
            room_name = str(row["room_name"]).strip()
            weekday = int(row["weekday"])
            sp = int(row["start_period"])
            ep = int(row["end_period"])
            sw = int(row["start_week"])
            ew = int(row["end_week"])
            course_name = str(row.get("course_name") or "课程占用").strip()
        except (KeyError, ValueError, TypeError):
            conflicts.append(f"第{idx}行: 字段缺失或格式错误")
            skipped += 1
            continue

        if room_name not in room_cache:
            room_cache[room_name] = db.scalar(select(Room).where(Room.name == room_name))
        room = room_cache[room_name]
        if not room:
            conflicts.append(f"第{idx}行: 实验室「{room_name}」不存在")
            skipped += 1
            continue
        if sp not in PERIOD_TIMES or ep not in PERIOD_TIMES:
            conflicts.append(f"第{idx}行: 节次 {sp}-{ep} 超出范围")
            skipped += 1
            continue

        start_t = PERIOD_TIMES[sp][0]
        end_t = PERIOD_TIMES[ep][1]

        for week in range(sw, ew + 1):
            day = term_start_monday + timedelta(weeks=week - 1, days=weekday - 1)
            start_dt = datetime.combine(day, start_t, tzinfo=timezone.utc)
            end_dt = datetime.combine(day, end_t, tzinfo=timezone.utc)
            try:
                create_booking(
                    db, room_id=room.id, user_id=operator_user_id,
                    start=start_dt, end=end_dt, purpose=course_name,
                    source="course", course_name=course_name, commit=False,
                )
                created += 1
            except ValueError:
                conflicts.append(f"第{idx}行 第{week}周: {room_name} {day} 时段冲突")
                skipped += 1

    db.commit()
    return {"created": created, "skipped": skipped, "removed": removed, "conflicts": conflicts}
