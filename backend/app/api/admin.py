"""管理员路由：看板、报表导出、预约审批、报修流转、课表导入、FAQ 维护、实验室管理。"""
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models.booking import Booking
from app.models.faq import FAQ
from app.models.repair import Repair
from app.models.room import Room
from app.models.user import User
from app.schemas.booking import BookingOut, BookingReview
from app.schemas.chat import FAQIn, FAQOut
from app.schemas.dashboard import DashboardOut
from app.schemas.document import DocumentImportResult, DocumentOut, PaginatedDocuments
from app.schemas.member import MemberOut, RoleUpdate
from app.schemas.repair import RepairOut, RepairTransition
from app.schemas.room import RoomCreate, RoomOut
from app.schemas.schedule import ScheduleImportResult
from app.services import document_service, report_service, repair_service
from app.services.dashboard_service import build_dashboard
from app.services.schedule_import import import_schedule

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx_response(content: bytes, *, ascii_name: str, display_name: str) -> Response:
    # 头部必须可 latin-1 编码：filename 用 ASCII 兜底，filename* 提供 UTF-8 中文名
    disposition = (f'attachment; filename="{ascii_name}"; '
                   f"filename*=UTF-8''{quote(display_name)}")
    return Response(content=content, media_type=XLSX_MIME,
                    headers={"Content-Disposition": disposition})


# ---------- 看板 ----------
@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db)):
    return build_dashboard(db)


# ---------- 报表导出 ----------
@router.get("/reports/bookings.xlsx")
def export_bookings(
    start: date | None = Query(None, description="起始日期 YYYY-MM-DD"),
    end: date | None = Query(None, description="结束日期 YYYY-MM-DD"),
    status: str | None = None,
    room_id: int | None = None,
    source: str | None = Query(None, description="user / course"),
    db: Session = Depends(get_db),
):
    content = report_service.build_bookings_report(
        db, start=start, end=end, status=status, room_id=room_id, source=source
    )
    suffix = f"_{start}_{end}" if start and end else ""
    return _xlsx_response(content, ascii_name=f"bookings{suffix}.xlsx",
                          display_name=f"预约报表{suffix}.xlsx")


@router.get("/reports/repairs.xlsx")
def export_repairs(
    start: date | None = Query(None, description="起始日期 YYYY-MM-DD"),
    end: date | None = Query(None, description="结束日期 YYYY-MM-DD"),
    status: str | None = None,
    room_id: int | None = None,
    db: Session = Depends(get_db),
):
    content = report_service.build_repairs_report(
        db, start=start, end=end, status=status, room_id=room_id
    )
    suffix = f"_{start}_{end}" if start and end else ""
    return _xlsx_response(content, ascii_name=f"repairs{suffix}.xlsx",
                          display_name=f"报修报表{suffix}.xlsx")


# ---------- 实验室管理 ----------
@router.post("/rooms", response_model=RoomOut)
def create_room(body: RoomCreate, db: Session = Depends(get_db)):
    room = Room(**body.model_dump())
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


# ---------- 预约审批 ----------
@router.get("/bookings", response_model=list[BookingOut])
def list_bookings(status: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Booking).order_by(Booking.start_time.desc())
    if status:
        stmt = stmt.where(Booking.status == status)
    out = []
    for b in db.scalars(stmt).all():
        o = BookingOut.model_validate(b)
        room = db.get(Room, b.room_id)
        user = db.get(User, b.user_id)
        o.room_name = room.name if room else None
        o.user_name = user.name if user else None
        out.append(o)
    return out


@router.post("/bookings/{booking_id}/review", response_model=BookingOut)
def review_booking(booking_id: int, body: BookingReview, db: Session = Depends(get_db)):
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(404, "预约不存在")
    if booking.status != "pending":
        raise HTTPException(400, "该预约不处于待审批状态")
    booking.status = "approved" if body.approve else "rejected"
    db.commit()
    db.refresh(booking)
    out = BookingOut.model_validate(booking)
    room = db.get(Room, booking.room_id)
    out.room_name = room.name if room else None
    return out


# ---------- 报修流转 ----------
@router.get("/repairs", response_model=list[RepairOut])
def list_repairs(status: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Repair).order_by(Repair.created_at.desc())
    if status:
        stmt = stmt.where(Repair.status == status)
    out = []
    for r in db.scalars(stmt).all():
        o = RepairOut.model_validate(r)
        room = db.get(Room, r.room_id)
        reporter = db.get(User, r.reporter_id)
        o.room_name = room.name if room else None
        o.reporter_name = reporter.name if reporter else None
        out.append(o)
    return out


@router.post("/repairs/{repair_id}/transition", response_model=RepairOut)
def transition_repair(repair_id: int, body: RepairTransition,
                      db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    repair = db.get(Repair, repair_id)
    if not repair:
        raise HTTPException(404, "报修单不存在")
    try:
        repair_service.transition(
            repair, new_status=body.status, operator=admin.name,
            note=body.note, handler_id=body.handler_id or admin.id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    db.commit()
    db.refresh(repair)
    o = RepairOut.model_validate(repair)
    room = db.get(Room, repair.room_id)
    o.room_name = room.name if room else None
    return o


# ---------- 课表批量导入 ----------
@router.post("/schedules/import", response_model=ScheduleImportResult)
async def import_schedules(
    file: UploadFile = File(...),
    term_start_monday: str = Form(..., description="学期第一周周一，YYYY-MM-DD"),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    try:
        start_monday = date.fromisoformat(term_start_monday)
    except ValueError:
        raise HTTPException(400, "term_start_monday 格式应为 YYYY-MM-DD")
    content = await file.read()
    try:
        result = import_schedule(
            db, content=content, filename=file.filename or "upload.csv",
            operator_user_id=admin.id, term_start_monday=start_monday,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return result


# ---------- FAQ 知识库 ----------
@router.get("/faqs", response_model=list[FAQOut])
def list_faqs(db: Session = Depends(get_db)):
    return list(db.scalars(select(FAQ)).all())


@router.post("/faqs", response_model=FAQOut)
def create_faq(body: FAQIn, db: Session = Depends(get_db)):
    faq = FAQ(**body.model_dump())
    db.add(faq)
    db.commit()
    db.refresh(faq)
    return faq


@router.put("/faqs/{faq_id}", response_model=FAQOut)
def update_faq(faq_id: int, body: FAQIn, db: Session = Depends(get_db)):
    faq = db.get(FAQ, faq_id)
    if not faq:
        raise HTTPException(404, "FAQ 不存在")
    for k, v in body.model_dump().items():
        setattr(faq, k, v)
    db.commit()
    db.refresh(faq)
    return faq


@router.delete("/faqs/{faq_id}")
def delete_faq(faq_id: int, db: Session = Depends(get_db)):
    faq = db.get(FAQ, faq_id)
    if not faq:
        raise HTTPException(404, "FAQ 不存在")
    db.delete(faq)
    db.commit()
    return {"ok": True}


# ---------- 成员管理 ----------
VALID_ROLES = {"student", "teacher", "admin"}


def _member_out(u: User) -> MemberOut:
    out = MemberOut.model_validate(u)
    out.is_whitelisted = u.sso_id in settings.admin_sso_id_set
    return out


@router.get("/users", response_model=list[MemberOut])
def list_users(keyword: str | None = None, role: str | None = None,
               db: Session = Depends(get_db)):
    stmt = select(User).order_by(User.role.desc(), User.id)
    if role:
        stmt = stmt.where(User.role == role)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where((User.name.like(like)) | (User.sso_id.like(like)))
    return [_member_out(u) for u in db.scalars(stmt).all()]


@router.put("/users/{user_id}/role", response_model=MemberOut)
def update_user_role(user_id: int, body: RoleUpdate, db: Session = Depends(get_db),
                     admin: User = Depends(get_current_admin)):
    if body.role not in VALID_ROLES:
        raise HTTPException(400, f"非法角色，仅支持 {VALID_ROLES}")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    # 防呆：不能取消自己的管理员权限，避免误操作把自己锁在外面
    if user.id == admin.id and body.role != "admin":
        raise HTTPException(400, "不能取消自己的管理员权限")
    # 白名单成员降级无意义（下次登录会被自动提升），直接拦截并提示
    if user.sso_id in settings.admin_sso_id_set and body.role != "admin":
        raise HTTPException(400, "该用户在管理员白名单中，请先从 ADMIN_SSO_IDS 配置移除")
    user.role = body.role
    db.commit()
    db.refresh(user)
    return _member_out(user)


# ---------- 知识文档（RAG） ----------
@router.get("/documents", response_model=PaginatedDocuments)
def list_documents(page: int = 1, page_size: int = 20, keyword: str | None = None,
                   db: Session = Depends(get_db)):
    items, total = document_service.list_documents(
        db, page=page, page_size=page_size, keyword=keyword)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/documents", response_model=DocumentOut)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    content = await file.read()
    try:
        status, doc = document_service.index_single(
            db, content=content, filename=file.filename or "upload.txt",
            title=title, uploaded_by=admin.id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    if status == "duplicate":
        raise HTTPException(409, f"该文档内容已存在：{doc.title}")
    return doc


@router.post("/documents/batch", response_model=DocumentImportResult)
async def upload_documents_zip(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    content = await file.read()
    try:
        return document_service.index_zip(db, content=content, uploaded_by=admin.id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/documents/reindex")
def reindex_documents(db: Session = Depends(get_db)):
    """用当前向量化方案重建所有文档索引（切换 EMBEDDING_PROVIDER 后调用）。"""
    return document_service.reindex_all(db)


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    if not document_service.delete_document(db, doc_id):
        raise HTTPException(404, "文档不存在")
    return {"ok": True}
