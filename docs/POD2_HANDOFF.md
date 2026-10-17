# POD-1 / POD-2 联调交接与回复草稿

2026-10-17；供 review。下表函数名称已对照代码，不是建议名。消息与讨论区回复仍为草稿，尚未发送。

## POD-1 可调用的真实入口

挂载 frontend/src/domain/RegistrationDomain.vue，传入登录域返回的 `session={token,role,id}`，通过组件 ref 调用：

| 函数 | POD-1 入口 |
| --- | --- |
| openCreateForm(activityId) | 发布者创建表单 |
| openFormTemplate(activityId) | 发布者查看/编辑模板 |
| openActivityRegistrations(activityId) | 已发布活动的报名名单 |
| openRegistration(activityId) | 学生活动详情/推文中的报名按钮 |
| openMyRegistrations() | 学生“我的报名” |
| openRegistrationDetail(record) | 我的报名记录详情；record 取自列表并包含 my_role |

事件：back、form-saved、registration-submitted、registration-cancelled。父页面据此返回或刷新；详情/取消由 POD-2 组件完成。详见 frontend/INTEGRATION.md 和 docs/POD2_API.md。

当前 frontend/src/views/RegistrationEntry.vue 仍是未传 session 的裸挂载。活动详情页也尚未挂载报名域和按钮。正式登录域与 POD-1 父页面接线仍需要共同完成；本次没有注入假会话、添加新认证接口或代替 POD-1 重写页面。

## 给 POD-1 的消息草稿

> 已按合并分支实际代码整理 POD-2 六个组件入口和八个报名 API，JSON 使用 field_key、extra_fields.team_extra、extra_fields.members[].member_extra。本次已补上 POD-1 活动详情裸 JSON 的适配，并将开发代理改为 127.0.0.1。请接入登录 session={token,role,id}，在活动页挂载 RegistrationDomain 后绑定报名/模板/名单按钮，并监听保存、提交、取消事件刷新页面。正式接口说明见 docs/POD2_API.md。推荐由 POD-2 自研，AI 打分正式接口名与契约另行确认；不增加报名导出/统计接口。

## 第一讨论区回复草稿

位置：[接口对齐讨论稿](https://my.feishu.cn/wiki/P8XEwKbDyiDErIk7HCRccbyRnxf)

> POD-2 已核对接口定稿、Schema v1.3 和 PM 最终回复，报名继续使用已定八个接口。取消前只读整队成员的 credentials，已有签到/凭证时返回 409 并线下处理；允许取消时物理删除并级联成员。活动 cancelled 禁止新报名但保留历史。报名导出/统计不进 MVP。推荐路径和 AI 打分契约已整理为待确认提案，尚未新增路由或表，待 PM/POD-1 确认后再实现。

## 第二讨论区回复草稿

位置：[PM 审阅意见与后续回复](https://my.feishu.cn/wiki/CBAMwCeFqiOjGVk9r8CcScOgnMj#doxcnXCopv54llihUkXAFjpeZRb)

> 已按最终回复统一 organizers、signup_deadline、comprehensive_score/conduct_score/innovation_score 和五态 status。表单沿用 form_team_schema/form_member_schema，报名保留 extra_fields 与 registration_members。仓库 main 与 POD-2 集成分支在本次拉取时同为 2219c8b，无需重复合并成员分支。本次改动在 codex/pod2-integration-review 供 review，具体接口 JSON 与校验见 docs/POD2_API.md；正式登录态和活动页按钮接线仍需与 POD-1 对齐。

## 推荐/画像提案：尚未批准、尚未实现

这是 S2 中“补推荐路径与 JSON”的具体候选方案；不改变八个已有报名接口。本周以已有模块联调为主，不将提案记为完成代码。

候选：GET/PUT `/api/users/{id}/profile`，仅本人；PUT 的 data 字段示例：

```json
{"major":"软件工程","grade":"2024级","interests":["算法"],"skills":["Python"],"need_comprehensive_score":1,"need_conduct_score":0,"need_innovation_score":1}
```

users 中 interests/skills 目前为逗号分隔 TEXT；是否在 API 中使用数组以及转换规则需确认。成功可返回 `{"code":0,"data":画像对象}`，不返回密码信息。

候选：POST `/api/recommendations`，当前用户由 token 识别；请求与响应示例：

```json
{"preferences":{"tags":["算法"],"need_innovation_score":1},"page":1,"page_size":20}
```

```json
{"code":0,"data":{"items":[{"activity_id":1,"score":0.83,"reasons":["兴趣匹配"]}],"total":1}}
```

activity_id 交给 POD-1 既有数据接口/展示组件；score 是算法结果，示例不是实际计算值。需确认展示组件是否接收 ID 列表、活动对象还是需适配，不能先宣布已联通。

画像打分流程另设业务入口（候选 POST `/api/users/{id}/profile/score`）：后端从库取本人画像，调用 POD-1 负责命名的 AI 打分网关，得到结果后持久化。网关请求候选：

```json
{"profile":{"major":"软件工程","grade":"2024级","interests":["算法"],"skills":["Python"],"need_comprehensive_score":1,"need_conduct_score":0,"need_innovation_score":1}}
```

网关纯数据响应候选：

```json
{"scores":{"algorithm":0.8},"source":"llm"}
```

维度、量纲、Mock/失败语义、版本/重算策略和结果存储位置均未定。当前 schema 没有已确认的评分结果存储字段，本次不新增表/列；须技术负责人批准具体迁移后再做“打分→存库”，不能只返回示例冒充实现。网关输出不套壳，业务 API 对前端包装一次 code/data。

申请 PM/POD-1 一次确认：上述新路径、字段与活动展示入参、AI 打分正式名称与语义、评分存储迁移。通知 POD-1 的最终消息应附获批契约与提交号。
