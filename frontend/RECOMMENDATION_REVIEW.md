# 陈珑珑：本周前端交付与 Review（2026-10-25）

对应飞书 POD-2 文档第 4–6 部分及 POD-1「推荐结果展示」回复。分支 `pod2/member-2`，PR 目标 `pod2/00-student-participation`；前端实现提交为 `1d43c79`。当日后续用户授权将 member-1 和 member-2 合入 00，合并前联合验证的补充结果见文末。

## 改动及入口

| 文件 | 变化 |
| --- | --- |
| `src/views/Recommend.vue`、`src/domain/recommendations.js` | 导入并使用 `<RecommendCards :items="items" />`；进入页评分；六标签初始全未选；切换标签、分页、重试；旧请求中断与版本检查，防止全取消标签后旧卡片重新出现 |
| `src/views/RecommendCards.vue`、`src/domain/recommendedActivities.js` | 沿用 POD-1 组件及 items 契约；按 ID 批量取完整活动，保留推荐顺序/理由；加载/错误/重试；隐藏已取消、已截止、非 published 或缺失的活动并给出提示 |
| `src/views/ActivityCard.vue` | 卡片支持 Tab 聚焦与 Enter 打开详情，保留原卡片样式 |
| `src/views/Browse.vue` | 取 published+ongoing，服务端分页每页 20 条，错误与重试；作为推荐无结果/评分失败时的入口 |
| `src/views/ActivityDetail.vue` | 学生点击返回列表回到 `/browse`，发布者回 `/activities`；沿用已有报名入口 |
| `src/views/Profile.vue`、`src/domain/profile.js` | 七字段只读查看→编辑→PUT→再次 GET→只读；失败保留输入，首次读取失败禁止空白覆盖；会话变化取消旧请求 |

同步依赖：`27c0bf1` 合入 POD-1 集成分支 `e6fbb67`，提供卡片、批量活动查询、现有登录/账号/推文等上游成果。PR 中后端、网关、账号等同步内容来自 POD-1；本次新增前端功能集中在后续 `feat(pod2)` 提交，Review 可先看该提交。本次没有新增业务接口或表。

## 路径、JSON 与状态码

所有业务成功响应 `{ "code": 0, "data": ... }`，错误 `{ "code": 4xx/5xx, "message": "..." }`；使用当前登录会话 Bearer token。

| 页面动作 | 请求 | data / JSON |
| --- | --- | --- |
| 读取画像 | `GET /api/users/{id}/profile` | 七字段和 id；允许未填写字段为 NULL |
| 保存画像 | `PUT /api/users/{id}/profile` | `{"major":"计算机","grade":"2024","interests":"算法,竞赛","skills":"Python,Vue","need_comprehensive_score":1,"need_conduct_score":1,"need_innovation_score":0}`；成功再 GET |
| 进入推荐、重新打分 | `POST /api/recommend/score` | 无 body；返回 `{"scored":28,"total":28}`（数字以实际为准） |
| 选择专业偏好 | `GET /api/recommend/list?match_major=1&match_interests=0&match_skills=0&need_conduct_score=0&need_innovation_score=0&need_comprehensive_score=0&page=1&page_size=20` | `{"items":[{"activity_id":34,"score":4,"scores":{"major":10,"interests":8,"skills":7},"reasons":["专业匹配"]}],"total":28}`（示例） |
| 卡片取全量信息 | `GET /api/activities?ids=34,29,24&page=1&page_size=100` | `{"items":[{...活动字段}],"total":3}`；按推荐 activity_id 对齐顺序 |
| 活动广场 | `GET /api/activities?status=published,ongoing&page=1&page_size=20` | `{"items":[{...活动字段}],"total":n}` |
| 通知查看/已读（现有 POD-1 页面） | `GET /api/notifications`；`PUT /api/notifications/{id}/read` | items/total；已读返回 `{"id":1,"is_read":1}` |

后端验证已核对：画像仅本人可读写（403），积分需求仅 0/1（400）；推荐仅学生（403），空画像（400），网关失败（502），偏好参数仅 0/1（400）。前端共用请求层处理 401 并清理会话；页面展示其余后端 message。报名状态与截止校验仍由原报名后端最终执行。

通知创建继续由 POD-2 后端在报名成功时内部调用 POD-1 `POST /api/notifications`。前端不创建通知。本次只验证现有通知列表/已读及用户隔离，未宣称报名后自动通知已完成。讨论中的 `title/created_at` 与当前实现的 `type/sent_at` 尚需两端后端统一。

## 已完成验证

- `npm test`：37/37，通过；新增 10 项覆盖请求契约、评分期间筛选、全取消/快速切换、旧会话响应、空画像、卡片查询失败/重试、排序/理由、NULL 画像及保存后刷新失败。
- `npm run build`：通过。沿用上游 md-editor 依赖，Vite 提示大 chunk；不影响构建成功。
- `node tests/live-api-smoke.mjs`：临时库运行真实后端，回归 8 个报名接口、所有者/队员限制、重复报名、表单锁定、取消及截止/取消状态。
- `node tests/live-recommendation-smoke.mjs`：临时库运行真实认证、画像、评分、列表、POD-1 批量活动接口、分页、活动广场、报名取消、通知列表/已读及用户隔离；覆盖 400/403/502 和恢复。
- 浏览器实测：登录→进入推荐全未选→选择专业→20 条卡片→第 2 页 8 条→Enter 打开详情→填写并成功报名→我的报名；画像编辑保存后只读；评分失败可重试并进入活动广场，广场第 2 页包含进行中活动；清空标签后空白。

评分服务使用测试夹具 `source=mock`，通过本地 HTTP 返回确定分值；正式后端的请求、解析、入库和筛选照常执行。没有调用真实 LLM，未验证线上部署或 AI 推荐质量，也未代表 POD-1 成员确认团队环境验收。

## 本地复验

先安装项目依赖。以下后端脚本会创建临时数据库，不使用或修改 `backend/campus.db`：

```powershell
# 在 frontend/ 下的终端 A
python tests/serve-backend.py --port 8014 --recommendations
# 终端 B
$env:VITE_DEV_API_TARGET='http://127.0.0.1:8014'
npm run dev -- --host 127.0.0.1 --port 5175 --strictPort
# 终端 C；每次接口复验先重启终端 A，取得全新临时库
node tests/live-recommendation-smoke.mjs
```

访问 `http://127.0.0.1:5175/recommend`。测试学生账号 `S1`（有画像）/`S2`（空画像），发布者 `review`，测试密码均为 `smoke123`。在测试画像技能中填 `force_gateway_error` 可以验证 502；改回普通内容后重新进入推荐页恢复。以上仅为临时环境夹具。

原报名回归使用另一份全新临时库：终端 A 执行 `python tests/serve-backend.py --port 8012`，终端 C 执行 `node tests/live-api-smoke.mjs`。

首次前端交付时的后端配合项为通知绑定、真实网关部署/算法优化和旧评分快照清理；通知绑定已在下述 member-1 联合验证中补齐。前端会过滤当前不可报名的卡片，但无法修复后端快照导致的候选总数偏差或资格变化；这些不计入本次前端完成项。

## member-1 / member-2 合并前联合验证（2026-10-25）

- 吸收 member-1 原始提交 `9bbf6316b6538b11e4bd55909bed204c3caa16d9`，保留报名成功向全队成员内部 HTTP 创建通知、匹配维度理由带分值的实现。积分需求单独勾选时不返回匹配理由。已有前端直接显示服务端理由。
- `serve-backend.py` 将 `BACKEND_BASE_URL` 指向自身临时端口。`live-api-smoke.mjs` 新增验证队长/队员分别收到一条报名通知，重复报名不增发；`live-recommendation-smoke.mjs` 验证分值理由及推荐→报名→真实内部 HTTP 通知链路。
- 联合代码 37/37 前端测试、生产构建和两组实际后端测试全部通过。通知创建使用真实后端接口及临时 SQLite；AI 分值仍为本地 HTTP 夹具，未验证真实 LLM 或团队部署环境。
- 合并方式：member-1 与 member-2 各自通过 PR 合入 `pod2/00-student-participation`，保留两边原始 commit 历史；PR 最终状态、合并 hash 和页面截图直接交给用户。没有改写飞书周报。
