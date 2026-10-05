# 对接文档 · member-3 → member-2（活动/推文 → FAQ 自动沉淀）

> 作者：POD-1 / member-3（智能答疑 + FAQ 知识库）
> 目的：你发布推文后，我这边**自动提取常见问答**存为「待审核」，管理员审核后上线。本文说明**你要调什么接口**、**活动接口的契约**。

## 1. 核心对接：推文发布成功后调一个接口

我提供了接口：

```
POST /api/faqs/auto-generate
Content-Type: application/json
```

**请求体**

```json
{
  "activity_id": 1,
  "title": "编程马拉松报名启动",
  "content": "编程马拉松10月20日18:00截止报名，3-5人组队，创新中心一楼，综测加0.5分……",
  "category": "竞赛类"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `activity_id` | 建议 | 你新建活动的真实 ID。传了才知道 FAQ 属于哪个活动 |
| `title` | 是 | 推文标题，我会记录来源，之后在 FAQ 里显示「← 编程马拉松报名启动」 |
| `content` | 是 | 推文**正文全文**（别只传摘要，AI 靠它提取问题） |
| `category` | 否 | 6 选 1：`竞赛类` `讲座/分享类` `培训/工作坊类` `招募类` `文体活动类` `通知类`，默认 `通知类` |

**响应**

```json
{
  "items": [ { "id": 12, "question": "…", "answer": "…", "source": "auto", "status": "draft" } ],
  "total": 3,
  "tip": "已存为草稿(draft)，请管理员审核修改后发布"
}
```

**返回的 FAQ 全是 `status=draft`（待审核），不会直接影响线上答疑**，所以你可以放心调。

## 2. 什么时候调 / 调几次

* 时机：**推文（`/api/ai/generate-article`）或活动发布成功后**
* 次数：**每个活动只调一次**（首次发布成功时）。重复调会先清掉该活动上一次的自动草稿再重生成，避免堆积
* 建议：调用放到后端，别在前端调；用 `try/except` 包一层，**提取失败不能影响你的发布流程**

参考伪代码：

```python
def on_publish_article(activity_id, title, content, category):
    try:
        requests.post("http://127.0.0.1:8000/api/faqs/auto-generate",
                      json={"activity_id": activity_id, "title": title,
                            "content": content, "category": category},
                      timeout=20)
    except Exception:
        pass  # 提取失败不影响发布
```

## 3. 活动接口的契约（重要）

为了让我这边的「活动名称下拉」能用，我在 `backend/activities.py` 临时放了两个最小接口：

```
GET  /api/activities      → {"items":[{"id":1,"title":"编程马拉松"}],"total":1}
POST /api/activities      → 传 {"title":"编程马拉松"} 建活动，返回 {"id":1,"title":"编程马拉松"}
```

**说明与请求：**

1. 活动域（`/api/activities` 的完整 CRUD）**归你（member-2）**，我的这两个是**占位/临时**，你做完完整版请**以你的为准**，我会改成调你的。
2. 请你保证 **`GET /api/activities` 至少返回 `[{id, title}]`** 这个契约，我的 FAQ 页靠它做「按活动名称筛选」和「新建 FAQ 时选活动」。
3. 我的 `POST /api/activities` 只接收 `{title}`，你覆盖后如果字段不同，告诉我，我改 FAQ 页的建活动逻辑。

## 4. 我这边已就绪（你可以自测）

* 接口地址：`http://localhost:8000/api/faqs/auto-generate`
* Swagger 文档：`http://localhost:8000/docs`（有 `POST /api/faqs/auto-generate`，可直接试）
* 命令行自测（PowerShell）：

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/faqs/auto-generate `
  -ContentType "application/json" `
  -Body '{"activity_id":1,"title":"编程马拉松报名启动","content":"编程马拉松10月20日截止，3-5人组队，创新中心一楼，有综测加分。","category":"竞赛类"}'
```

返回 `total=3` 即成功。之后你可以去 `http://localhost:5173/faqs` 点状态「待审核」看到这批数据。

## 5. 数据流（整体）

```
你发布推文 → 调 /api/faqs/auto-generate
   → member-3 用 AI(现为Mock网关) 提取 3-5 条问答
   → 存为 source=auto, status=draft（待审核）
   → 管理员在 FAQ 页修改并「审核发布」
   → 答疑端立即可命中
```

## 6. 背景：AI 能力来自 member-1 的网关服务（你无需操心）

我这个 `auto-generate` 接口内部会调用 **member-1 的 AI 网关服务**（独立 HTTP 服务，默认 `http://127.0.0.1:8100`）的 `/api/ai/extract-faq` 来做推文提取：

```
你 → POST /api/faqs/auto-generate → member-3 后端 → HTTP → 网关服务 /api/ai/extract-faq
```

对你的影响：

* **你不用直接调网关**，只管调我的 `auto-generate`
* 网关没开 / 没配 Key 时，我这边自动降级为模板提问，**接口照样返回，不报错**
* 你自己的推文生成 `/api/ai/generate-article` 也用同一个网关服务，地址同样默认 `127.0.0.1:8100`

> **@member-2 注意**：你最初写的网关 `main.py` 返回是 `{"code":0,"data":{...}}`，我为了全项目接口格式统一，改成了**直接返回内容**（如 `/api/ai/chat` 返回 `{"answer","source"}`）。这个壳**没有还原** —— 你接前端时请按"直接返回内容"解析；如果你坚持要 `code/data` 壳，提前说，我们统一后再一起改。

如果你在本地跑，需要 member-1 先把网关服务起来（`cd 网关; uvicorn main:app --port 8100`），否则大家走的都是 Mock。详见 `docs/对接-member1-AI网关.md`。

## 7. 验收清单

- [ ] 发布推文后调用，返回 `total >= 1`
- [ ] FAQ 页「状态=待审核」能看到刚生成的数据，来源显示 `auto` + 推文标题
- [ ] `activity_id` 用的是真实活动 ID（不是写死 1）
- [ ] 重复调用同一活动，不会重复堆积草稿
- [ ] 提取失败时你的发布流程不受影响

## 8. 暂不需要你做的

* FAQ 的增删改查、审核、答疑逻辑全部归我，你不用管
* 你只需保证上面一个调用 + `GET /api/activities` 契约即可
