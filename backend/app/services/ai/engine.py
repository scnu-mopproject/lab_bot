"""咨询引擎：混合检索（FAQ + 文档）+ LLM 生成。"""
from sqlalchemy.orm import Session

from app.services.ai.base import RetrievedDoc
from app.services.ai.providers import get_provider
from app.services.ai.retriever import FAQRetriever, VectorRetriever

SYSTEM_BASE = (
    "你是学院实验室管理智能助手，负责解答场地预约、设备报修、实验室使用等业务咨询。"
    "回答需简洁、准确、友好，使用中文。请优先依据下方提供的参考资料作答；若资料不足，请如实说明并提示联系管理员。"
)


def _build_system(docs: list[RetrievedDoc]) -> str:
    if not docs:
        return SYSTEM_BASE
    refs = []
    for d in docs:
        if d.kind == "document":
            refs.append(f"- 摘自《{d.title}》：{d.content}")
        else:
            refs.append(f"- 问：{d.title}\n  答：{d.content}")
    return f"{SYSTEM_BASE}\n\n【参考资料】\n" + "\n\n".join(refs)


def _merge(faq_docs: list[RetrievedDoc], vec_docs: list[RetrievedDoc],
           top_k: int = 5) -> list[RetrievedDoc]:
    merged = sorted([*faq_docs, *vec_docs], key=lambda d: d.score, reverse=True)
    return merged[:top_k]


async def answer_question(db: Session, *, message: str, history: list[dict]) -> dict:
    faq_docs = FAQRetriever(db).search(message, top_k=3)
    vec_docs = VectorRetriever(db).search(message, top_k=4)
    docs = _merge(faq_docs, vec_docs, top_k=5)
    system = _build_system(docs)

    messages = [*history, {"role": "user", "content": message}]
    reply = await get_provider().generate(system=system, messages=messages)

    return {
        "reply": reply,
        "sources": [{"question": d.title, "score": d.score, "kind": d.kind} for d in docs],
    }
