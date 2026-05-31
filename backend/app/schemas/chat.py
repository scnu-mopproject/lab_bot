from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # user / assistant
    content: str


class ChatIn(BaseModel):
    message: str
    history: list[ChatMessage] = []


class ChatSource(BaseModel):
    question: str
    score: float


class ChatOut(BaseModel):
    reply: str
    sources: list[ChatSource] = []


class FAQIn(BaseModel):
    question: str
    answer: str
    category: str | None = None
    keywords: str | None = None


class FAQOut(FAQIn):
    id: int

    model_config = {"from_attributes": True}
