"""AI 抽象层：LLMProvider 与 Retriever 接口。

接真实模型（Claude / 通义 / 智谱等）只需实现 LLMProvider.generate 并在
get_provider() 中注册，业务代码无需改动。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RetrievedDoc:
    title: str        # FAQ 问题 或 文档标题
    content: str      # FAQ 答案 或 文档片段内容
    score: float
    kind: str = "faq"  # faq | document


class Retriever(ABC):
    @abstractmethod
    def search(self, query: str, top_k: int = 3) -> list[RetrievedDoc]:
        ...


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, *, system: str, messages: list[dict]) -> str:
        """messages: [{"role": "user"/"assistant", "content": str}]"""
        ...
