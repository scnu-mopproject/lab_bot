"""向量化（embedding）抽象层，可插拔。

- local（默认）：纯 Python 的哈希词袋向量，**零依赖、可离线**，无需下载模型，
  适合开箱即用与本地/校内合规场景。检索质量为词面级，够用作 v1。
- bge：本地 sentence-transformers 中文向量模型（需自行 `pip install sentence-transformers`
  并下载模型），语义检索质量高，数据不出本地。
- openai-compatible：调用云端 embedding API（通义/智谱/OpenAI 兼容），简单、效果好，
  但文本片段会发送到云端，敏感数据需评估。

切换向量化方案后需对已上传文档**重建索引**（不同方案向量维度/语义不一致）。
"""
import hashlib
import math
import re
from abc import ABC, abstractmethod

from app.core.config import settings

_EN = re.compile(r"[a-z0-9]+")
_ZH = re.compile(r"[一-鿿]")


def tokenize(text: str) -> list[str]:
    """中英混合分词：英文按词，中文按单字 + 2-gram。"""
    text = text.lower()
    toks = _EN.findall(text)
    zh = _ZH.findall(text)
    toks.extend(zh)
    toks.extend(zh[i] + zh[i + 1] for i in range(len(zh) - 1))
    return toks


class EmbeddingProvider(ABC):
    name: str = "base"

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


class LocalHashingEmbedding(EmbeddingProvider):
    """哈希词袋 + 子线性 TF + L2 归一化。确定性、离线、无需模型。"""

    name = "local"

    def __init__(self, dim: int | None = None):
        self.dim = dim or settings.embedding_dim

    def _hash(self, token: str) -> int:
        return int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % self.dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            vec = [0.0] * self.dim
            counts: dict[int, int] = {}
            for tok in tokenize(t):
                idx = self._hash(tok)
                counts[idx] = counts.get(idx, 0) + 1
            for idx, cnt in counts.items():
                vec[idx] = 1.0 + math.log(cnt)  # 子线性 TF
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


class BGEEmbedding(EmbeddingProvider):
    """本地中文向量模型（sentence-transformers，按需安装）。"""

    name = "bge"

    def embed(self, texts: list[str]) -> list[list[float]]:
        from sentence_transformers import SentenceTransformer

        if not hasattr(self, "_model"):
            self._model = SentenceTransformer(settings.embedding_model or "BAAI/bge-small-zh-v1.5")
        vecs = self._model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vecs]


class OpenAICompatibleEmbedding(EmbeddingProvider):
    """云端 embedding（OpenAI 兼容端点，如通义千问 text-embedding-v3 / 智谱）。"""

    name = "cloud"
    BATCH = 10  # DashScope 等对单次 input 数量有限制，分批更稳

    def embed(self, texts: list[str]) -> list[list[float]]:
        import httpx

        headers = {"Authorization": f"Bearer {settings.embedding_api_key}"}
        url = f"{settings.embedding_base_url.rstrip('/')}/embeddings"
        out: list[list[float]] = []
        with httpx.Client(timeout=60) as client:
            for i in range(0, len(texts), self.BATCH):
                batch = texts[i:i + self.BATCH]
                resp = client.post(url, headers=headers,
                                   json={"model": settings.embedding_model, "input": batch})
                resp.raise_for_status()
                # 按返回的 index 排序，保证与输入顺序一致
                data = sorted(resp.json()["data"], key=lambda d: d.get("index", 0))
                out.extend(item["embedding"] for item in data)
        return out


def get_embedding_provider() -> EmbeddingProvider:
    mapping = {
        "local": LocalHashingEmbedding,
        "bge": BGEEmbedding,
        "openai-compatible": OpenAICompatibleEmbedding,
    }
    return mapping.get(settings.embedding_provider, LocalHashingEmbedding)()


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)
