"""咨询引擎：RAG 检索 + LLM 生成。"""
from sqlalchemy.orm import Session

from app.services.ai.base import RetrievedDoc
from app.services.ai.providers import get_provider
from app.services.ai.retriever import FAQRetriever

SYSTEM_BASE = (
    "你是学院实验室管理智能助手，负责解答场地预约、设备报修、实验室使用等业务咨询。"
    "回答需简洁、准确、友好，使用中文。若参考资料不足，请提示用户联系管理员。"
)


def _build_system(docs: list[RetrievedDoc]) -> str:
    if not docs:
        return SYSTEM_BASE
    refs = "\n\n".join(f"- 问：{d.question}\n  答：{d.answer}" for d in docs)
    return f"{SYSTEM_BASE}\n\n【参考资料】\n{refs}"


async def answer_question(db: Session, *, message: str, history: list[dict]) -> dict:
    retriever = FAQRetriever(db)
    docs = retriever.search(message, top_k=3)
    system = _build_system(docs)

    messages = [*history, {"role": "user", "content": message}]
    provider = get_provider()
    reply = await provider.generate(system=system, messages=messages)

    return {
        "reply": reply,
        "sources": [{"question": d.question, "score": d.score} for d in docs],
    }
