"""业务咨询机器人路由。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.chat import ChatIn, ChatOut
from app.services.ai import answer_question

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatOut)
async def chat(body: ChatIn, db: Session = Depends(get_db),
               _: User = Depends(get_current_user)):
    history = [{"role": m.role, "content": m.content} for m in body.history][-10:]
    result = await answer_question(db, message=body.message, history=history)
    return result
