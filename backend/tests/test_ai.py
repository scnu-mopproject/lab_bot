"""向量化/LLM 相关单元测试（不依赖外部网络，用假 httpx）。"""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mktemp(suffix='.db')}")
os.environ.setdefault("SSO_MOCK", "true")


class _FakeResp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


class _FakeClient:
    """模拟云端 embedding：返回乱序 index + 以文本长度为标记的向量。"""
    calls = 0

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, headers=None, json=None):
        _FakeClient.calls += 1
        inp = json["input"]
        data = [{"index": i, "embedding": [float(len(t))]} for i, t in enumerate(inp)]
        return _FakeResp({"data": list(reversed(data))})  # 故意乱序


def test_cloud_embedding_batches_and_orders(monkeypatch):
    from app.core.config import settings
    settings.embedding_base_url = "http://fake/v1"
    settings.embedding_model = "text-embedding-v3"
    settings.embedding_api_key = "k"
    monkeypatch.setattr("httpx.Client", _FakeClient)
    _FakeClient.calls = 0

    from app.services.ai.embedding import OpenAICompatibleEmbedding
    emb = OpenAICompatibleEmbedding()
    texts = ["a" * n for n in range(1, 24)]  # 23 条，长度 1..23
    out = emb.embed(texts)

    # 顺序被正确还原（尽管响应乱序）
    assert [v[0] for v in out] == [float(len(t)) for t in texts]
    # 23 条按 BATCH=10 分 3 次请求
    assert _FakeClient.calls == 3
