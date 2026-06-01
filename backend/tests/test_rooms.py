"""场地管理：CRUD、停用联动取消/迁移、改约；课表重导覆盖。"""
import io
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mktemp(suffix='.db')}")
os.environ.setdefault("SSO_MOCK", "true")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import init_db  # noqa: E402
from app.main import app  # noqa: E402

init_db()
client = TestClient(app)


def _login(sso_id, role="admin"):
    r = client.post("/api/auth/dev-login", json={"sso_id": sso_id, "name": sso_id, "role": role})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _mk_room(admin, name):
    return client.post("/api/admin/rooms", headers=admin, json={"name": name, "capacity": 10}).json()["id"]


def _book(headers, room_id, h_start, h_end, day="2031-03-03"):
    return client.post("/api/bookings", headers=headers, json={
        "room_id": room_id,
        "start_time": f"{day}T{h_start}:00:00+00:00",
        "end_time": f"{day}T{h_end}:00:00+00:00",
        "purpose": "实验",
    })


def test_room_crud_and_disable_relocate():
    admin = _login("rmadmin", "admin")
    stu = _login("rmstu", "student")
    src = _mk_room(admin, "源场地")
    dst = _mk_room(admin, "目标场地")

    # 列表（管理端，含计数）
    rooms = client.get("/api/admin/rooms", headers=admin).json()
    assert any(r["id"] == src and "future_bookings" in r for r in rooms)

    # 编辑
    r = client.put(f"/api/admin/rooms/{src}", headers=admin, json={"capacity": 99})
    assert r.status_code == 200 and r.json()["capacity"] == 99

    # 两个未来预约：09-10 可迁移，10-11 在目标场地会冲突
    b1 = _book(stu, src, "09", "10").json()
    b2 = _book(stu, src, "10", "11").json()
    # 在目标场地先占住 10-11，制造迁移冲突
    _book(stu, dst, "10", "11")

    # 影响预检
    impact = client.get(f"/api/admin/rooms/{src}/impact", headers=admin).json()
    assert impact["user_bookings"] == 2

    # 停用 + 迁移到目标场地
    r = client.patch(f"/api/admin/rooms/{src}/active?active=false", headers=admin,
                     json={"action": "relocate", "target_room_id": dst})
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["relocated"] == 1                       # b1 迁移成功
    assert len(res["conflicts"]) == 1                  # b2 冲突，交管理员
    assert res["conflicts"][0]["id"] == b2["id"]

    # b1 已改到目标场地并带说明
    mine = client.get("/api/bookings/mine", headers=stu).json()
    b1_now = next(b for b in mine if b["id"] == b1["id"])
    assert b1_now["room_id"] == dst and "改约" in (b1_now["system_note"] or "")

    # 源场地已停用，不在师生可见列表
    assert all(rm["id"] != src for rm in client.get("/api/rooms", headers=stu).json())

    # 冲突预约出现在"待改约"列表
    conflicts = client.get("/api/admin/bookings/conflicts", headers=admin).json()
    assert any(c["id"] == b2["id"] for c in conflicts)

    # 手动改约处理冲突的 b2 -> 改到 11-12
    r = client.put(f"/api/admin/bookings/{b2['id']}/relocate", headers=admin,
                   json={"room_id": dst, "start_time": "2031-03-03T11:00:00+00:00",
                         "end_time": "2031-03-03T12:00:00+00:00"})
    assert r.status_code == 200 and r.json()["room_id"] == dst

    # 处理后"待改约"列表清空
    assert client.get("/api/admin/bookings/conflicts", headers=admin).json() == []

    # 两条预约都已迁走，源场地无关联记录 -> 可物理删除
    assert client.delete(f"/api/admin/rooms/{src}", headers=admin).status_code == 200


def test_disable_cancel_and_hard_delete():
    admin = _login("rmadmin2", "admin")
    stu = _login("rmstu2", "student")
    rid = _mk_room(admin, "待取消场地")
    b = _book(stu, rid, "14", "15", day="2031-04-04").json()

    # 停用 + 取消全部
    r = client.patch(f"/api/admin/rooms/{rid}/active?active=false", headers=admin,
                     json={"action": "cancel", "reason": "设备搬迁"})
    assert r.json()["cancelled"] == 1
    mine = client.get("/api/bookings/mine", headers=stu).json()
    assert next(x for x in mine if x["id"] == b["id"])["status"] == "cancelled"

    # 仍存在（已取消的）预约记录：普通删除被拦，提示需强制
    assert client.delete(f"/api/admin/rooms/{rid}", headers=admin).status_code == 409
    # impact 暴露历史记录数，未来有效为 0
    imp = client.get(f"/api/admin/rooms/{rid}/impact", headers=admin).json()
    assert imp["future_bookings"] == 0 and imp["total_bookings"] == 1
    # 强制删除可成功（级联清除历史）
    assert client.delete(f"/api/admin/rooms/{rid}?force=true", headers=admin).status_code == 200

    # 空场地直接物理删除
    empty = _mk_room(admin, "空场地")
    assert client.delete(f"/api/admin/rooms/{empty}", headers=admin).status_code == 200


def test_delete_blocked_by_future_booking():
    admin = _login("delfut", "admin")
    stu = _login("delfutstu", "student")
    rid = _mk_room(admin, "有未来预约室")
    _book(stu, rid, "09", "10", day="2032-06-06")
    # 有未来有效预约：即便 force 也不允许删除，须先停用处理
    assert client.delete(f"/api/admin/rooms/{rid}", headers=admin).status_code == 409
    assert client.delete(f"/api/admin/rooms/{rid}?force=true", headers=admin).status_code == 409


def test_admin_cancel_booking():
    admin = _login("cxadmin", "admin")
    stu = _login("cxstu", "student")
    rid = _mk_room(admin, "改约取消室")
    b = _book(stu, rid, "08", "09", day="2031-05-05").json()
    r = client.post(f"/api/admin/bookings/{b['id']}/cancel", headers=admin,
                    json={"reason": "临时占用"})
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    mine = client.get("/api/bookings/mine", headers=stu).json()
    assert next(x for x in mine if x["id"] == b["id"])["system_note"] == "临时占用"


def test_schedule_reimport_replaces():
    admin = _login("scadmin", "admin")
    _mk_room(admin, "课表室X")
    csv_data = ("room_name,weekday,start_period,end_period,start_week,end_week,course_name\n"
                "课表室X,1,1,2,1,2,高数\n")

    def _import():
        return client.post("/api/admin/schedules/import", headers=admin,
                           files={"file": ("s.csv", io.BytesIO(csv_data.encode()), "text/csv")},
                           data={"term_start_monday": "2031-09-01"}).json()

    r1 = _import()
    assert r1["created"] == 2 and r1["removed"] == 0 and not r1["conflicts"]
    # 重导（覆盖）：应先清空上次（removed=2），再新建，不再自我冲突
    r2 = _import()
    assert r2["created"] == 2 and r2["removed"] == 2 and not r2["conflicts"]


def test_mine_excludes_course():
    """课表占用不应出现在导入者的「我的预约」里。"""
    admin = _login("mineadmin", "admin")
    _mk_room(admin, "课表室Z")
    csv = ("room_name,weekday,start_period,end_period,start_week,end_week,course_name\n"
           "课表室Z,1,1,2,1,3,高数\n")
    client.post("/api/admin/schedules/import", headers=admin,
                files={"file": ("s.csv", io.BytesIO(csv.encode()), "text/csv")},
                data={"term_start_monday": "2031-09-01", "mode": "append"})
    mine = client.get("/api/bookings/mine", headers=admin).json()
    assert all(b["source"] == "user" for b in mine)
    assert not any(b["course_name"] == "高数" for b in mine)


def test_schedule_template_download():
    admin = _login("tpladmin", "admin")
    r = client.get("/api/admin/schedules/template.xlsx", headers=admin)
    assert r.status_code == 200 and len(r.content) > 1000
    assert "spreadsheet" in r.headers["content-type"]


def test_schedule_append_mode():
    admin = _login("scadmin2", "admin")
    _mk_room(admin, "课表室Y")

    def _imp(course, mode):
        csv = ("room_name,weekday,start_period,end_period,start_week,end_week,course_name\n"
               f"课表室Y,1,1,2,1,2,{course}\n")
        return client.post("/api/admin/schedules/import", headers=admin,
                           files={"file": ("s.csv", io.BytesIO(csv.encode()), "text/csv")},
                           data={"term_start_monday": "2031-09-01", "mode": mode}).json()

    a = _imp("高数", "append")
    assert a["created"] == 2 and a["removed"] == 0      # 追加：不清空
    # 再追加相同时段的另一门课 -> 时段已占用，全部跳过（防重复/防撞）
    b = _imp("线代", "append")
    assert b["created"] == 0 and b["removed"] == 0 and len(b["conflicts"]) == 2
