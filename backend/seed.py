"""初始化演示数据：管理员、实验室、FAQ。

运行：  python seed.py
"""
from sqlalchemy import select

from app.core.database import SessionLocal, init_db
from app.models.faq import FAQ
from app.models.room import Room
from app.models.user import User

ROOMS = [
    {"name": "计算机实验室 A301", "location": "理科楼 A 区 3 楼", "capacity": 60,
     "description": "通用机房，60 台终端", "open_time": "08:00", "close_time": "22:00"},
    {"name": "人工智能实验室 B205", "location": "理科楼 B 区 2 楼", "capacity": 40,
     "description": "GPU 工作站 + 实验设备", "open_time": "08:00", "close_time": "21:00"},
    {"name": "电子工程实验室 C108", "location": "工科楼 C 区 1 楼", "capacity": 30,
     "description": "示波器、信号发生器等", "open_time": "09:00", "close_time": "20:00"},
]

FAQS = [
    {"question": "如何预约实验室？", "category": "预约",
     "keywords": "预约,场地,会议室,流程",
     "answer": "进入小程序「场地预约」，选择实验室与日期，点击空闲时段格子选择起止时间后提交即可。若开启审批，需等待管理员通过。"},
    {"question": "预约后可以取消吗？", "category": "预约", "keywords": "取消,预约,退订",
     "answer": "可以。在「我的预约」中找到对应记录，点击取消即可释放时段。"},
    {"question": "设备坏了如何报修？", "category": "报修", "keywords": "报修,设备,损坏,维修",
     "answer": "进入「设备报修」，选择实验室、填写设备名称与故障描述并上传照片后提交。管理员会分配处理并更新进度。"},
    {"question": "报修进度在哪里查看？", "category": "报修", "keywords": "进度,报修,状态,查询",
     "answer": "在「设备报修」列表点击对应工单，可查看从提交、受理、维修中到完成的完整时间线。"},
    {"question": "实验室开放时间是什么时候？", "category": "使用", "keywords": "开放,时间,几点",
     "answer": "各实验室开放时间不同，一般为 08:00-22:00，具体以预约页面显示的开放时段为准。"},
]


def run() -> None:
    init_db()
    db = SessionLocal()
    try:
        if not db.scalar(select(User).where(User.sso_id == "admin")):
            db.add(User(sso_id="admin", name="实验室管理员", role="admin", college="人工智能学院"))
        for r in ROOMS:
            if not db.scalar(select(Room).where(Room.name == r["name"])):
                db.add(Room(**r))
        for f in FAQS:
            if not db.scalar(select(FAQ).where(FAQ.question == f["question"])):
                db.add(FAQ(**f))
        db.commit()
        print("演示数据已初始化：管理员(sso_id=admin) / 3 个实验室 / 5 条 FAQ")
    finally:
        db.close()


if __name__ == "__main__":
    run()
