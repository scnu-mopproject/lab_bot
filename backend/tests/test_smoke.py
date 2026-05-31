"""冒烟测试：登录 → 建房 → 预约冲突 → 报修流转 → 咨询。

运行：  cd backend && pip install -r requirements.txt pytest && pytest
（使用临时 SQLite，互不影响）
"""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mktemp(suffix='.db')}")
os.environ.setdefault("SSO_MOCK", "true")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import init_db  # noqa: E402
from app.main import app  # noqa: E402

init_db()
client = TestClient(app)


def _login(sso_id="admin", role="admin"):
    r = client.post("/api/auth/dev-login", json={"sso_id": sso_id, "name": "T", "role": role})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_full_flow():
    admin = _login("admin", "admin")
    student = _login("stu001", "student")

    # 管理员建实验室
    r = client.post("/api/admin/rooms", headers=admin,
                    json={"name": "测试室", "capacity": 10})
    assert r.status_code == 200
    room_id = r.json()["id"]

    # 学生预约
    payload = {"room_id": room_id, "start_time": "2030-01-01T09:00:00+00:00",
               "end_time": "2030-01-01T10:00:00+00:00", "purpose": "实验"}
    r = client.post("/api/bookings", headers=student, json=payload)
    assert r.status_code == 200, r.text

    # 冲突预约应被拒绝
    r = client.post("/api/bookings", headers=student, json=payload)
    assert r.status_code == 409

    # 可用性查询
    r = client.get(f"/api/rooms/{room_id}/availability?date=2030-01-01", headers=student)
    assert r.status_code == 200
    slots = r.json()["slots"]
    assert any(not s["available"] for s in slots)

    # 报修 + 流转
    r = client.post("/api/repairs", headers=student,
                    json={"room_id": room_id, "device_name": "投影仪", "description": "无法开机"})
    assert r.status_code == 200
    rid = r.json()["id"]
    r = client.post(f"/api/admin/repairs/{rid}/transition", headers=admin,
                    json={"status": "assigned", "note": "已分配"})
    assert r.status_code == 200
    assert r.json()["status"] == "assigned"
    # 非法流转
    r = client.post(f"/api/admin/repairs/{rid}/transition", headers=admin,
                    json={"status": "done"})
    assert r.status_code == 400

    # 咨询
    client.post("/api/admin/faqs", headers=admin,
                json={"question": "如何预约实验室", "answer": "进入场地预约页面操作", "keywords": "预约,场地"})
    r = client.post("/api/chat", headers=student, json={"message": "怎么预约实验室？"})
    assert r.status_code == 200
    assert r.json()["reply"]
