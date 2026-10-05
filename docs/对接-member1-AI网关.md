# 对接文档 · member-3 → member-1（AI 网关服务）

> 作者：POD-1 / member-3（智能答疑 + FAQ 知识库）
> 对接方式：**方案 2 —— 网关作为独立 HTTP 服务**，member-3 的后端通过 HTTP 调用 `/api/ai/*`。
> 目的：答疑、"推文 FAQ 自动生成"、"高频问题同义匹配"三处 AI 能力都走你的网关服务。

## 1. 总览：三个 AI 接入点

member-3 有三处要用 AI，全部走你的网关服务：

| # | member-3 的位置 | 调用的网关接口 | 网关函数 |
|---|---|---|---|
| ① | 智能答疑（未命中 FAQ 时兜底） | `POST /api/ai/chat` | `chat(question)` |
| ② | 推文 AI 提取 FAQ | `POST /api/ai/extract-faq` | `extract_faq(title, content, count)` |
| ③ | 高频问题同义沉淀 | `POST /api/ai/similar-question` | `similar_question(question, candidates)` |

## 2. 网关初版已经给你了（`网关/`）

| 文件 | 说明 |
|---|---|
| `网关/ai_gateway.py` | 网关封装，含三个能力函数 + 统一入口，内置 Mock 降级 |
| `网关/main.py` | **独立服务入口**，暴露 `/api/ai/*` 接口 |
| `网关/.env.example` | 环境变量模板，复制成 `.env` 填写 |

**启动方式**

```bash
cd 网关
uvicorn main:app --reload --port 8100
```

默认走 Mock；在 `网关/.env` 设 `USE_REAL_LLM=1` 并填 Key 后走真实大模型（百炼 qwen-plus）。

## 3. 接口契约（请你保持这些路径/字段不变）

member-3 的 `backend/llm_gateway.py` 是按下面的契约写的 HTTP 客户端，**改路径或字段我这边就会调不通**。

### ① 智能答疑

```
POST /api/ai/chat
请求：{"question": "报名截止什么时候？", "activity_id": 1}
响应：{"answer": "10月20日18:00截止。", "source": "llm"}
```

* `source`：真实模型返回 `"llm"`，Mock/降级返回 `"mock"`

### ② 推文关键问题提取

```
POST /api/ai/extract-faq
请求：{"title": "编程马拉松报名启动", "content": "推文正文全文……", "count": 5}
响应：{"items": [{"question": "...", "answer": "..."}, ...]}
```

### ③ 同义 / 相似问题匹配

```
POST /api/ai/similar-question
请求：{"question": "什么时候不能报名了", "candidates": ["报名截止什么时候", "在哪举办"]}
响应：{"index": 0}        # 最相似候选的下标；都不相似返回 -1
```

### 兼容说明（已保留 member-2 早期写法）

* `generate_text(prompt, system=None)` 和 `chat(question, system=None)` **保留了可选的 `system` 参数**，不传也能用
* `AI_MOCK=true` 仍然生效（等价于 `USE_REAL_LLM=0`，强制 Mock）
* `_recommend_by_llm` helper 已保留，`recommend` 逻辑复原

### 注意：接口返回壳变了（@member-2 请看）

member-2 最初 `main.py` 的返回是 `{"code":0,"data":{...}}`，我为了让所有接口格式统一（与 `backend` 一致），改成了**直接返回内容**：

| 接口 | member-2 原来 | 现在 |
|---|---|---|
| `/api/ai/chat` | `{"code":0,"data":{"answer","source"}}` | `{"answer","source"}` |
| `/api/ai/generate-article` | `{"code":0,"data":{"content"}}` | `{"content"}` |
| `/api/ai/recommend` | `{"code":0,"data":{"items"}}` | `{"items"}` |

**这个壳没还原**（还原会和我 backend 的调用对不上）。member-2 如果要接前端，请按"直接返回内容"来解析；若坚持要 `code/data` 壳，请提前说，我们统一后再改两边。

### 附：其它（供 member-2 用）

```
POST /api/ai/generate-article   {"activity_id":1,"style":"简约"} -> {"content": "..."}
POST /api/ai/recommend          {"user_id":1}                   -> {"items": [...]}
```

## 4. 关键要求：必须可降级、不能 hang

三个接入点都在**用户请求链路**上，网关若超时/报错直接抛异常会导致：

* 答疑页卡住
* 发布推文后 FAQ 提取失败，流程中断

要求：**网络异常、超时、Key 失效时返回兜底内容（或可控异常），不要 hang 死。** 超时建议 ≤ 15s。

我这边已经做了降级（网关不可用时用本地 Mock），但请你也保证网关自身不抛未捕获异常。

## 5. 环境变量约定

**网关侧（`网关/.env`）**

```
USE_REAL_LLM=1
DASHSCOPE_API_KEY=sk-你的key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus
```

**我这边（`backend/.env`）**

```
USE_REAL_LLM=1
AI_GATEWAY_URL=http://127.0.0.1:8100
```

* `AI_GATEWAY_URL` 指向你的网关服务地址，我据此发 HTTP 请求
* Key 只放你那边，**我这边不需要 Key**

## 6. 验收清单（联调时逐条过）

- [ ] `GET http://127.0.0.1:8100/api/hello` 返回 `{"message":"ai gateway ok"}`
- [ ] `POST /api/ai/chat` 返回 `{"answer","source"}`
- [ ] `POST /api/ai/extract-faq` 返回 `{"items":[{"question","answer"}]}`
- [ ] `POST /api/ai/similar-question` 返回 `{"index": 数字}`
- [ ] 关掉网关后，我这边答疑/提取仍能返回（降级 Mock），不报 500
- [ ] 真实模式下（`USE_REAL_LLM=1`）返回的是真实模型内容，不是 Mock 前缀

## 7. 我这边已就绪、不依赖你的部分

* FAQ 知识库 CRUD（`/api/faqs`）——已跑通
* 答疑"先查 FAQ"、高频沉淀、赞/踩反馈——已跑通
* 以上用 Mock 就能演示，**你不阻塞我，我也不阻塞你**

## 8. 对齐分工方案

按《POD-1分工方案》：你第 1 周交付「网关接口定义 + Mock」，我对着 Mock 开发；第 2 周末接真实网关。

**现在只差你：**
1. 确认上面 3 个 HTTP 接口的路径/字段（有异议提前说，我改客户端）
2. 把网关服务在 8100 跑起来（或告诉我你的端口）
3. 真实网关调通后，我这边设 `USE_REAL_LLM=1` + `AI_GATEWAY_URL` 即可切换，业务代码不再改
