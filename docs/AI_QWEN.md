# 接入通义千问（让问答更聪明）

问答分两块，可分别接通义千问（阿里云百炼 / DashScope，**OpenAI 兼容**）：
1. **生成回答**（LLM）：把检索到的资料交给 `qwen-plus` 等模型生成自然语言答案。质量提升最大。
2. **文档检索**（embedding，可选）：用 `text-embedding-v3` 做语义向量，召回更准。

> 前提：在[阿里云百炼](https://bailian.console.aliyun.com/)开通服务、创建 **API-KEY**（形如 `sk-xxx`）。

## 一、只接「生成回答」（推荐先做这步）

编辑 `backend/.env`：

```
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus
LLM_API_KEY=sk-你的百炼APIKey
```

重启后端即可。此时**检索仍用本地向量**（离线），但回答由通义千问生成——大多数场景这一步就够"聪明"了。

可选模型：`qwen-turbo`（快、便宜）/ `qwen-plus`（均衡，推荐）/ `qwen-max`（最强）。

## 二、再接「文档检索」用 Qwen 向量（语义检索）

继续在 `.env` 增加：

```
EMBEDDING_PROVIDER=openai-compatible
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v3
EMBEDDING_API_KEY=sk-你的百炼APIKey
```

**重要**：切换向量化方案后，已上传文档的旧向量（local）与新方案不兼容，需**重建索引**：
- 小程序：管理后台 → 知识库 → 管理文档 → 右上「**重建索引**」
- 或调接口：`POST /api/admin/documents/reindex`

重建后，文档检索即变为通义千问的语义向量。

## 三、合规提醒

接云端后，**提问内容与检索到的文档片段会发送到阿里云**。若文档含敏感信息：
- 可只接「生成回答」、检索仍用本地/`bge`（数据不出本地的折中）；
- 或评估后再决定是否将文档 embedding 也上云。

## 四、排错

- 回答变成"智能回答服务暂时不可用…"：说明 LLM 调用失败（key 错/无网/模型名错/欠费）。检查 `LLM_API_KEY`、`LLM_MODEL`、网络。系统已做降级，不会 500，会退回展示检索内容。
- embedding 报错：确认 `text-embedding-v3` 模型名与 base_url 正确；大文档已自动分批（每批 10 条）。
- 切了 embedding 但问答召回不到文档：八成是**忘了重建索引**。
