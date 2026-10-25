# 画像、推荐与评分：前端交接 v0.1

本轮是 POD-2 第三周设计契约交付。报名联调的已实现代码与验证见 [MEMBER2_REVIEW.md](MEMBER2_REVIEW.md)。画像/推荐路由与评分存储（`activity_scores` 表）已实现并接入导航（`/profile`、`/recommend`）；AI 打分网关 `/api/ai/score` 由 POD-1 实现，尚未上线。

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
{"code":0,"data":{"items":[{"activity_id":1,"score":8.4,"scores":{"major":9,"interests":8,"skills":8},"reasons":["专业匹配得分9/10","兴趣得分8/10","技能锻炼得分8/10"]}],"total":1}}
```

前端把 activity_id 交给 POD-1 活动展示组件，不从推荐响应臆造活动标题/推文；空结果显示空状态，不以示例活动填充。总分由 POD-2 业务后端计算，前端不再排序计算第二份分数。

## AI 评分调用边界

POD-2 业务后端调用网关；浏览器不直连大模型、不持有网关密钥。评分路径 `/api/ai/score` 是讨论稿占位，正式名称由 POD-1 确认。请求为 `{profile,activity}`，专业/兴趣/技能分为 0～10；积分需求是否命中用 0/10 表达。网关返回纯数据，由业务后端包装一次 code/data。

```json
{"eligible":10,"scores":{"major":9,"interests":8,"skills":8,"conduct":0,"innovation":10,"comprehensive":10},"source":"llm"}
```

## 页面状态约定

| 场景 | 前端行为 |
| --- | --- |
| 初次读取画像 | 加载状态，不用空白表单覆盖尚未返回的数据 |
| 保存画像中 | 禁止重复提交；失败保留输入，只有保存成功后提示成功 |
| 推荐请求中 | 显示加载，不将旧筛选结果标为新结果；切换筛选丢弃旧请求 |
| 评分超时/失败 | 展示后端失败原因与重试入口，不显示伪造评分或“已推荐” |
| 无画像 | 引导补充画像，不静默发送默认个人资料 |
| 无候选活动 | items=[]、total=0，显示空状态 |
| 登录失效 | 清理共享会话，关闭个人数据弹窗 |

已定稿：评分结果持久化到 `activity_scores` 表、评分接口 `POST /api/recommend/score`（点推荐页触发全量重打分）、权重归一 0.4/0.3/0.3、前 50% 阈值（综合分 ≥ 选中权重总分×50%）、并列按综合分降序→活动 ID 降序。仍待定稿：网关异常状态码/超时时间。未定稿状态码不由前端自造。
