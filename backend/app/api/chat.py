"""业务咨询机器人路由。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.chat_log import ChatLog
from app.models.user import User
from app.schemas.chat import ChatIn, ChatOut
from app.services.ai import answer_question

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatOut)
async def chat(body: ChatIn, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    history = [{"role": m.role, "content": m.content} for m in body.history][-10:]
    result = await answer_question(db, message=body.message, history=history)

    # 记录提问用于高频问题统计（命中 FAQ 时记录其问题，便于聚合）
    sources = result.get("sources") or []
    db.add(ChatLog(
        user_id=user.id,
        message=body.message[:512],
        matched_question=sources[0]["question"] if sources else None,
    ))
    db.commit()
    return result
