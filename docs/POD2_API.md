# POD-2 报名接口与校验说明

核对日期：2026-10-17。代码基线：`2219c8b`；本次修订分支：`codex/pod2-integration-review`。
本文以已读取的飞书接口定稿、Schema v1.3、PM 10/11 回复和仓库实际实现为依据。八个报名接口沿用现有路径、JSON 和 HTTP 状态，不新增数据库表。

## 通用约定

- 请求头：`Authorization: Bearer <token>`；JSON 请求使用 `Content-Type: application/json`。
- 成功均为 HTTP 200，`{"code":0,"data":...}`；失败为对应 HTTP 4xx，`{"code":HTTP状态码,"message":"原因"}`。
- Pydantic/分页参数错误由现有公共处理器返回 HTTP 400、`{"code":400,"message":"参数错误"}`，不是 FastAPI 默认的 detail/422。
- 分页：`page>=1`、`1<=page_size<=100`，默认 1/20；返回 `data.items` 与 `data.total`。
- Schema v1.3 明确 `max_participants` 为**队伍数**，单队人数由 min_team_member/max_team_member 限制，均含队长。
- 截止时间读取 signup_deadline，支持 ISO 8601 的时区、小数秒与 Z。无时区按服务端本地时区解释；空值不限，无法解析返回 400。
- 身份/活动归属由服务端校验；客户端不传 user_id、organizer_id、form_id 来决定写入身份或表单。
- 当前开发鉴权为 `student:<id>` / `organizer:<id>`；公共正式登录域尚未接入，报名组件接收已有 session，不伪造登录。

## 请求 JSON

### F：创建/修改表单

```json
{
  "form_team_schema":[
    {"field_key":"project_name","label":"项目名称","type":"text","required":true}
  ],
  "form_member_schema":[
    {"field_key":"student_id","label":"学号","type":"text","required":true},
    {"field_key":"name","label":"姓名","type":"text","required":true},
    {"field_key":"intro","label":"个人介绍","type":"textarea","required":false}
  ]
}
```

field_key 和 label 不能为空，同一 schema 中 key 不重复；类型仅 text/textarea。队员固定字段 student_id/name 的题干、text 类型和必填不能更改。队伍 schema 可以为空，队员 schema 必须包含固定两项。自定义题目 field_key 使用前端现有拼音生成器，编辑题干后不重建既有 key。

### R：提交报名

```json
{
  "extra_fields":{
    "team_extra":{"project_name":"示例项目"},
    "members":[
      {"role":"captain","member_extra":{"student_id":"S1","name":"示例队长","intro":""}},
      {"role":"member","member_extra":{"student_id":"S2","name":"示例队员","intro":""}}
    ]
  }
}
```

只有 extra_fields 一个顶层键；第一名必须 captain，其余 member。身份通过学号匹配已注册 users；队长学号必须属于当前 token 用户。所有答案为字符串，必填不能空白。前端只提交 schema 中字段，UI 标识不发送。数据库 extra_fields 存同一 JSON；成员身份另外落 registration_members，并由 UNIQUE(activity_id,user_id) 限制同活动只能加入一队。

## 八个报名接口

| 编号 | 方法和路径 | 调用身份 | 请求体 | 成功 data |
| --- | --- | --- | --- | --- |
| R01 | POST `/api/activities/{id}/forms` | 本活动 organizer | F | `{"form_id":11}` |
| R02 | GET `/api/activities/{id}/forms` | 已登录用户 | 无 | Form，见下文 |
| R03 | PUT `/api/activities/{id}/forms` | 本活动 organizer | F | `{"form_id":11}` |
| R04 | GET `/api/activities/{id}/registrations` | 本活动 organizer | 无；query 分页 | ActivityRegistrationList |
| R05 | POST `/api/activities/{id}/registrations` | student/队长 | R | `{"registration_id":21}` |
| R06 | GET `/api/users/{id}/registrations` | 对应本人 student | 无；query 分页 | MyRegistrationList |
| R07 | GET `/api/registrations/{registration_id}` | 报名队长或队员 | 无 | RegistrationDetail |
| R08 | DELETE `/api/registrations/{registration_id}` | 队长 | 无 | `null`，完整响应 `{"code":0,"data":null}` |

### R02 的 Form

```json
{
  "code":0,
  "data":{
    "form_id":11,"organizer_id":8,
    "form_team_schema":[{"field_key":"project_name","label":"项目名称","type":"text","required":true}],
    "form_member_schema":[{"field_key":"student_id","label":"学号","type":"text","required":true},{"field_key":"name","label":"姓名","type":"text","required":true}],
    "min_team_member":1,"max_team_member":4,"created_at":"2026-10-17T10:00:00"
  }
}
```

发布者预览/编辑与学生填写共用这份数据，由前端区分渲染模式。当前 GET 只要求登录，尚未实现按活动可见状态限制读表单；不将更严格的可见性描述为已经实现。

### R04 的 ActivityRegistrationList

```json
{"code":0,"data":{"items":[{"registration_id":21,"user_id":101,"registered_at":"2026-10-17T10:05:00","extra_fields":{"team_extra":{"project_name":"示例项目"},"members":[{"role":"captain","member_extra":{"student_id":"S1","name":"示例队长"}}]}}],"total":1}}
```

user_id 为队长 ID，列表以报名单分页；成员答案已在 extra_fields.members 中，不再假设顶层 members/id 字段。

### R06 的 MyRegistrationList

```json
{"code":0,"data":{"items":[{"registration_id":21,"activity_name":"示例活动","activity_status":"published","registered_at":"2026-10-17T10:05:00","my_role":"member"}],"total":1}}
```

按 registration_members 查询，因此队员和队长都能查到自己的报名；只能查询当前用户。活动 cancelled 后历史仍在列表中。

### R07 的 RegistrationDetail

```json
{
  "code":0,
  "data":{
    "registration_id":21,"activity_id":1,"form_id":11,
    "activity_name":"示例活动","activity_status":"published",
    "registered_at":"2026-10-17T10:05:00","my_role":"captain",
    "form":{
      "form_team_schema":[{"field_key":"project_name","label":"项目名称","type":"text","required":true}],
      "form_member_schema":[{"field_key":"student_id","label":"学号","type":"text","required":true},{"field_key":"name","label":"姓名","type":"text","required":true}],
      "min_team_member":1,"max_team_member":4
    },
    "extra_fields":{"team_extra":{"project_name":"示例项目"},"members":[{"role":"captain","member_extra":{"student_id":"S1","name":"示例队长"}}]}
  }
}
```

详情适配已经由 frontend/src/domain/adapters.js 实现；POD-1 不需要另写适配器。现有详情接口仅学生队伍成员可读，发布者通过 R04 查看名单。

## 后端校验与状态码

| 操作/条件 | HTTP/code | 处理 |
| --- | --- | --- |
| 未登录、token 无效、身份资源不存在 | 401 | 走共同认证错误提示 |
| 非本活动发布者、查询他人列表、非成员看详情、队员取消 | 403 | 服务端拒绝 |
| 活动/表单/报名不存在 | 404 | 返回可读原因 |
| 同活动重复创建表单或成员重复报名 | 409 | 整体回滚，不留下半成品 |
| 参数/答案类型错误、分页越界 | 400 | 公共参数错误壳 |
| 固定题目不合法、必填空白、队长顺序/身份不符、人数不合法、未注册学号 | 400 | 返回具体校验提示 |
| 已有报名后修改表单 | 400 | 完全禁止修改，沿用现有业务 |
| 活动非 published、过截止时间、无效截止时间、队伍名额已满 | 400 | 拒绝报名 |
| 取消时已过截止或 finished | 400 | 沿用现有取消限制 |
| 整队任一成员已有凭证/签到 | 409 | “已签到或已发凭证，请线下处理” |

报名仅 published 可新提交，五态 draft/published/ongoing/finished/cancelled 的其他四态均拒绝。对 cancelled 的历史保留规则与“队长主动取消报名物理删除”是两个不同操作。

报名、创建/修改表单、取消报名在 SQLite BEGIN IMMEDIATE 事务中先校验再写入，避免并发穿过名额、表单锁定或凭证检查。每次 POD-2 数据库连接启用 foreign_keys，删除 registrations 后级联删除 registration_members。

取消检查按 activity_id 和**整队所有 user_id** 读取 credentials；该表没有 registration_id。status 为 issued/confirmed/signed 或 checkin_time 非空时阻止取消。只读凭证，不作废、不删除、不写凭证、不发送取消事件。

未知异常不在本次修复中全局改写成业务错误；前端已有非 JSON 失败通用提示。POD-1 活动/FAQ 等接口的整体响应统一由技术负责人协调。

## POD-1 活动详情兼容点

仓库 `backend/activity/activities.py:get_activity` 当前返回裸活动对象，而报名请求层默认只接受 code/data。因此仅 `createRegistrationApi().getActivity(id)` 显式允许这一裸对象；也兼容将来改成统一壳的版本。非 2xx 或带非零 code 仍失败，八个报名接口不放宽验壳。

## 来源

- [POD-2 原文档](https://vcnq1au0eity.feishu.cn/docx/P3QddJx55o6xaixSiBAcrPOQnO1)
- [接口定稿](https://my.feishu.cn/wiki/JdNrwdE4cisdj8k5CLPc5rsPnHh)
- [Schema v1.3](https://my.feishu.cn/wiki/JvrjwVgGdiTYPUkZ5dJcydDxnzg)
- [接口讨论稿](https://my.feishu.cn/wiki/P8XEwKbDyiDErIk7HCRccbyRnxf)
- [第二讨论区与 PM 最终回复](https://my.feishu.cn/wiki/CBAMwCeFqiOjGVk9r8CcScOgnMj)
- [POD2 第二周周报](https://my.feishu.cn/wiki/Qz69wRrRciR20DkzjHMcLc4xnXb)
