"""LLMProvider 实现与工厂。默认 Mock；预留 Claude / OpenAI 兼容接口。"""
from app.core.config import settings
from app.services.ai.base import LLMProvider


class MockLLMProvider(LLMProvider):
    """无需外部模型：基于检索内容拼装回答，用于框架占位与本地联调。"""

    async def generate(self, *, system: str, messages: list[dict]) -> str:
        user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        # system 中已包含检索到的 FAQ 上下文，这里做模板化回答
        if "【参考资料】" in system:
            return (
                "根据实验室管理规定，为你解答：\n\n"
                + system.split("【参考资料】", 1)[1].strip()
                + "\n\n（如未完全解决，请联系实验室管理员或在「业务咨询」继续追问。）"
            )
        return f"已收到你的问题：「{user_msg}」。暂未在知识库中找到对应条目，建议联系管理员咨询。"


class ClaudeProvider(LLMProvider):
    """接入 Anthropic Claude（需安装 anthropic 并配置 LLM_API_KEY）。"""

    async def generate(self, *, system: str, messages: list[dict]) -> str:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=settings.llm_api_key)
        resp = await client.messages.create(
            model=settings.llm_model or "claude-sonnet-4-6",
            max_tokens=1024,
            system=system,
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
        )
        return "".join(block.text for block in resp.content if block.type == "text")


class OpenAICompatibleProvider(LLMProvider):
    """接入 OpenAI 兼容接口（通义/智谱/文心等多有兼容端点）。"""

    async def generate(self, *, system: str, messages: list[dict]) -> str:
        import httpx

        payload = {
            "model": settings.llm_model,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                json=payload, headers=headers,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]


def get_provider() -> LLMProvider:
    mapping = {
        "mock": MockLLMProvider,
        "claude": ClaudeProvider,
        "openai-compatible": OpenAICompatibleProvider,
    }
    return mapping.get(settings.llm_provider, MockLLMProvider)()
