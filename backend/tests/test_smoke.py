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

    # 看板
    r = client.get("/api/admin/dashboard", headers=admin)
    assert r.status_code == 200
    dj = r.json()
    assert dj["summary"]["open_repairs"] >= 0
    assert "submitted" not in dj["repair_status"] or dj["repair_status"]["assigned"] >= 1
    assert any(h["question"] for h in dj["hot_questions"])  # 提问已被统计

    # 看板需管理员
    assert client.get("/api/admin/dashboard", headers=student).status_code == 403

    # 报表导出（Excel）
    r = client.get("/api/admin/reports/bookings.xlsx?start=2030-01-01&end=2030-12-31", headers=admin)
    assert r.status_code == 200
    assert r.content[:2] == b"PK"  # xlsx = zip
    assert "spreadsheetml" in r.headers["content-type"]
    r = client.get("/api/admin/reports/repairs.xlsx", headers=admin)
    assert r.status_code == 200 and r.content[:2] == b"PK"


def test_member_and_whitelist():
    from app.core.config import settings

    settings.admin_sso_ids = "boss001"  # 直接改单例实例，property 即时生效

    # 白名单用户即便以 student 登录也会被提升为 admin
    r = client.post("/api/auth/dev-login", json={"sso_id": "boss001", "name": "B", "role": "student"})
    boss = r.json()
    assert boss["user"]["role"] == "admin"
    admin = {"Authorization": f"Bearer {boss['access_token']}"}

    # 准备一个普通用户
    client.post("/api/auth/dev-login", json={"sso_id": "stuA", "name": "A", "role": "student"})
    users = client.get("/api/admin/users", headers=admin).json()
    by_sso = {u["sso_id"]: u for u in users}
    assert by_sso["boss001"]["is_whitelisted"] is True
    assert by_sso["stuA"]["is_whitelisted"] is False

    # 提升 / 降级普通用户
    sid = by_sso["stuA"]["id"]
    assert client.put(f"/api/admin/users/{sid}/role", headers=admin, json={"role": "admin"}).json()["role"] == "admin"
    assert client.put(f"/api/admin/users/{sid}/role", headers=admin, json={"role": "student"}).json()["role"] == "student"

    # 防呆：不能降自己；不能降白名单成员；非法角色
    boss_id = by_sso["boss001"]["id"]
    assert client.put(f"/api/admin/users/{boss_id}/role", headers=admin, json={"role": "student"}).status_code == 400
    assert client.put(f"/api/admin/users/{sid}/role", headers=admin, json={"role": "x"}).status_code == 400

    # 非管理员无权访问
    stu = {"Authorization": f"Bearer {client.post('/api/auth/dev-login', json={'sso_id': 'stuZ', 'name': 'Z', 'role': 'student'}).json()['access_token']}"}
    assert client.get("/api/admin/users", headers=stu).status_code == 403


def test_document_rag():
    import io

    admin = _login("admin", "admin")
    student = _login("docstu", "student")

    text = (
        "实验室安全管理规定。\n"
        "进入实验室必须佩戴防护眼镜和实验服。\n"
        "危险化学品须存放在专用试剂柜，使用后立即归位并登记。\n"
        "发生火情应立即使用就近灭火器并拨打安保电话。\n"
    )
    files = {"file": ("safety.txt", io.BytesIO(text.encode("utf-8")), "text/plain")}
    r = client.post("/api/admin/documents", headers=admin, files=files,
                    data={"title": "实验室安全管理规定"})
    assert r.status_code == 200
    doc = r.json()
    assert doc["chunk_count"] >= 1 and doc["embedding_model"] == "local"

    # 文档列表 + 非管理员不可上传
    assert len(client.get("/api/admin/documents", headers=admin).json()) >= 1
    assert client.post("/api/admin/documents", headers=student, files=files).status_code == 403

    # 提问应召回该文档片段
    r = client.post("/api/chat", headers=student, json={"message": "危险化学品怎么存放"}).json()
    assert any(s["kind"] == "document" for s in r["sources"])

    # 删除
    assert client.delete(f"/api/admin/documents/{doc['id']}", headers=admin).status_code == 200
