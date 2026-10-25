# 画像、推荐与评分：前端交接 v0.2

更新日期：2026-10-25。画像/推荐页面已实现，推荐结果已接入 POD-1 的 RecommendCards。报名原交付见 [MEMBER2_REVIEW.md](MEMBER2_REVIEW.md)，本次变化与验证见 [RECOMMENDATION_REVIEW.md](RECOMMENDATION_REVIEW.md)。POD-1 已提供 AI 评分网关代码；本轮用临时数据库及本地 HTTP 评分夹具验证调用链，未验证团队部署的真实 AI 服务。

## 前端字段与业务 API

| UI 内容 | 字段/格式 | 请求位置 |
| --- | --- | --- |
| 专业、年级 | major、grade：字符串 | GET/PUT /api/users/{id}/profile |
| 兴趣、技能 | interests、skills：v0.1 沿用逗号分隔字符串 | 同上 |
| 三类积分需求 | need_comprehensive_score、need_conduct_score、need_innovation_score：0/1 | 同上 |
| 专业/兴趣/技能匹配开关 | match_major、match_interests、match_skills：0/1 | GET /api/recommend/list 的 query |
| 推荐分页 | page=1、page_size=20 | 同上 |
| 推荐积分偏好 | 上述三个 need_*，0/1 | 同上 |

画像 PUT 只提交以上七字段，不传 role/password/id；GET 返回同组字段及 id。成功响应使用 `{code:0,data:...}`；学生身份来自登录 token。GET 推荐不发送 JSON body。

画像示例：

```json
{"major":"软件工程","grade":"2024级","interests":"算法,竞赛","skills":"Python","need_comprehensive_score":1,"need_conduct_score":0,"need_innovation_score":1}
```

推荐响应的显示字段：

```json
{"code":0,"data":{"items":[{"activity_id":1,"score":8.4,"scores":{"major":9,"interests":8,"skills":8},"reasons":["兴趣匹配"]}],"total":1}}
```

前端把 activity_id 交给 POD-1 活动展示组件，不从推荐响应臆造活动标题/推文；空结果显示空状态，不以示例活动填充。总分由 POD-2 业务后端计算，前端不再排序计算第二份分数。

## AI 评分调用边界

进入推荐页时浏览器调用 `POST /api/recommend/score`，成功后按当前标签调用列表接口。POD-2 业务后端通过内部 HTTP 调用 POD-1 的 `/api/ai/score`；浏览器不直连大模型、不持有网关密钥。请求为 `{profile,activity}`，专业/兴趣/技能分为 0～10；积分需求是否命中用 0/10 表达。网关返回纯数据，由业务后端包装一次 code/data。

```json
{"eligible":10,"scores":{"major":9,"interests":8,"skills":8,"conduct":0,"innovation":10,"comprehensive":10},"source":"llm"}
```

## 页面状态约定

| 场景 | 前端行为 |
| --- | --- |
| 初次读取画像 | GET 成功后只读展示七字段；新账号的 NULL 显示为未填写/否；读取失败只允许重试 |
| 编辑、保存画像 | 点击编辑进入输入态，隐藏顶部返回/编辑按钮；底部保存；PUT 成功后再次 GET，再回到查看态；失败保留草稿 |
| 保存成功但重新读取失败 | 明确提示已保存，重新加载只发送 GET，避免重复提交 |
| 未选择推荐标签 | 六个标签默认全未选，保持空白；不会发送列表请求 |
| 推荐请求中 | 显示加载，不将旧筛选结果标为新结果；切换筛选丢弃旧请求 |
| 评分超时/失败 | 展示后端失败原因与重试入口，不显示伪造评分或“已推荐” |
| 无画像 | 引导补充画像，不静默发送默认个人资料 |
| 无候选活动 | items=[]、total=0，显示空状态 |
| 登录失效 | 清理共享会话，关闭个人数据弹窗 |

现有后端实现：`POST /api/recommend/score` 写入 `activity_scores`；专业/兴趣/技能权重 0.4/0.3/0.3，阈值为选中权重之和 × 10 × 50%，按综合分降序、活动 ID 降序。前端保留这一顺序；不参与评分或重新排序。后端网关请求超时为 10 秒，调用或响应异常映射为 502；无画像返回 400。前端显示后端 message，提供重试和活动广场入口。
