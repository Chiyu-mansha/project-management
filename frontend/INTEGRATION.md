# POD-2 报名前端对接

依据 POD-2 文档及 2026-10-17 本周清单，陈珑珑负责报名域前端及与 POD-1 的入口接线。本分支已挂载活动详情页的报名/表单/名单入口、接入共享会话，并统一活动列表/详情的只读请求；报名八接口和后端表结构保持不变。画像、推荐及 AI 评分本轮交付设计契约，见 [前端字段与评分交接](SCORING_CONTRACT.md)。

## 已执行的约定

- 8 个报名接口的路径、方法保持不变。POST/PUT JSON 使用报名文档第 7 节的字段。
- 最新成功响应为 `{ "code": 0, "data": ... }`；错误为 `{ "code": 4xx/5xx, "message": "..." }`。早期 `code:200/msg` 已被定稿覆盖。
- 每次请求携带 `Authorization: Bearer <token>`。会话由登录域传入；登录态写入 localStorage（键 `pod2.session`），刷新后仍保持登录。
- 列表携带 `page/page_size`。兼容已提供的两种列表数据：报名第 7 节的 `data: []` 与最新分页的 `data: { items, total }`；不会接受猜测的其他结构。
- 新建模板只读调用 POD-1 `GET /api/activities/{id}`，读取人数；学生打开报名时重新检查状态和 `signup_deadline`。只有 published 且未截止时允许报名，后端仍作最终校验。
- 表单题目完全按 schema 渲染，输入值原样提交。固定学号、姓名锁定；同一 schema 内 key 唯一；两个 schema 独立。
- 第一张成员卡片固定为队长，成员总人数含队长，个人活动隐藏角色及成员增删操作。
- 修改前使用活动报名列表检查已有报名；最终并发校验由 PUT 后端负责。
- 取消整队报名仅向 DELETE 接口发请求。已签到/已发凭证的检查由报名后端只读 credentials 表执行；前端显示后端的 `message`，失败不关闭弹窗，不调用凭证或通知域接口。

## 接入 POD-1

在已有页面挂载 `RegistrationDomain.vue`，传入登录接口返回的 `{ token, role, id }`：

```vue
<script setup>
import { ref } from 'vue'
import RegistrationDomain from './domain/RegistrationDomain.vue'

const registrationDomain = ref(null)
// session 使用已有登录状态，不在报名域重新实现登录。
</script>

<template>
  <RegistrationDomain
    ref="registrationDomain"
    :session="session"
    @back="returnToPublishedActivities"
    @form-saved="refreshPublishedActivities"
    @registration-submitted="refreshActivity"
  />
</template>
```

供文档指定的按钮调用：

| 函数 | 入口 |
| --- | --- |
| `openCreateForm(activityId)` | 发布方创建报名表单 |
| `openFormTemplate(activityId)` | 发布方查看模板，弹窗内编辑 |
| `openActivityRegistrations(activityId)` | 发布方查看报名列表，返回时触发 `back` |
| `openRegistration(activityId)` | 学生在活动推文页点击报名 |
| `openMyRegistrations()` | 当前登录学生查看自己的报名 |
| `openRegistrationDetail(record)` | 查看我的报名记录，保留列表返回的 my_role |

也可使用 `home` 作用域插槽装入 POD-1 的原页面。打开列表时隐藏该插槽，返回时恢复，未新增约定外的路由或活动编辑页面。

### 活动页直接使用的入口组件

`ActivityDetail.vue` 已使用 `ActivityRegistrationActions.vue`。其他活动页面可以同样接入：

```vue
<ActivityRegistrationActions
  :activity="activity"
  :session="session"
  @session-expired="clearSession"
  @form-saved="refreshActivity"
  @registration-submitted="refreshActivity"
  @registration-cancelled="refreshActivity"
/>
```

`activity` 使用已有活动详情对象，至少包含 `id/organizer_id/status/signup_deadline`。组件仅向该活动发布者展示表单和名单按钮；向学生展示报名及我的报名。取消、截止及其他非 published 状态禁用报名；到达截止时间后按钮会更新。表单保存/报名/取消事件为 `{ activity_id, form_id? / registration_id? }`，父页面据此刷新；域组件原六函数及原事件参数保持兼容。

### 正式登录状态的接入点

```js
import { session, setSession, clearSession } from './auth/session.js'
// 现有登录接口成功后：
setSession(loginResult.data) // { token, role, id }，不自行生成 token
// 退出后：
clearSession()
```

全应用使用同一会话（内存 + localStorage 持久化，刷新后仍登录）；student/organizer 的大小写统一，ID 校验后保留。`RegistrationEntry.vue` 在学生进入时自动加载我的报名。HTTP/业务 401 通过 `session-expired` 通知宿主清理会话；切换身份或离开页面会关闭旧弹窗、取消旧查询，并丢弃旧响应。

正式认证接口已交付：`POST /api/auth/register`、`POST /api/auth/login`（按 role 分叉，学生用学号+密码、发布者用工号+密码），登录返回 `{ token, role, id }` 后调用 `setSession`。原 `/api/dev/token` 与“开发联调登录”面板已删除。

## 已补齐的两项对接

### 题干生成拼音 field_key

用户于 2026-10-14 确认使用拼音规则。`fieldKeys.js` 使用本地 `pinyin-pro` 生成小写、无声调、下划线分隔的拼音，例如“联系电话”→ `lian_xi_dian_hua`。英文、数字保留，空白和标点归一为下划线，`ü` 用 `v`；数字开头加 `field_` 前缀。纯标点题干给出填写提示。

正式组件自带生成器，无需外部传函数。保存时预留该 schema 的全部已有 key；重复或同音题目自动添加 `_2`、`_3` 等后缀。两个 schema 独立。生成后保留 key，编辑题干不会重建标识，已有报名答案仍按原 key 展示。原 `generateFieldKey(label)` 注入入口保留兼容，返回值可为 Promise。

### GET /api/registrations/{id} 的详情适配

默认适配器位于 `adapters.js`，与合并分支 `backend/registrations.py:get_registration` 的实际响应对应。API 层先解开 `{ code: 0, data }`，适配器读取以下路径：

| 后端 data 中的路径 | 前端展示数据 |
| --- | --- |
| `form.form_team_schema` | `teamSchema` |
| `form.form_member_schema` | `memberSchema` |
| `extra_fields.team_extra` | `teamExtra` |
| `extra_fields.members` | `members` |
| `form.min_team_member` 和 `form.max_team_member` 均为 1 | `isIndividual` |

未传 `readRegistrationDetail` 也能查看详情。保留原注入入口兼容已有调用方；异常响应明确提示加载失败，允许重试。

取消按钮依据“我的报名”接口中的 `my_role` 显示。队长取消成功后刷新列表，后端拒绝取消时保留详情弹窗及线下处理提示。

## 本地验证

```powershell
cd frontend
npm install
npm test
npm run build
npm run dev
```

开发 `/api` 默认代理到 `http://127.0.0.1:8000`，避免 Windows IPv6 localhost 问题。可用 `VITE_API_BASE_URL` 配置 API base、`VITE_DEV_API_TARGET` 配置开发代理目标。活动列表/详情使用同一代理；仅活动只读适配允许历史裸 JSON，八个报名接口仍严格要求 code/data。

### 使用临时数据库跑真实联调

在仓库已有 Python 后端环境中，从 frontend 目录启动：

```powershell
python tests/serve-backend.py --port 8012
```

另一个终端验证八接口（使用该脚本新建的测试库，执行一次后如需重跑先重启后端）：

```powershell
node tests/live-api-smoke.mjs
$env:VITE_DEV_API_TARGET='http://127.0.0.1:8012'
npm run dev -- --host 127.0.0.1 --port 5175
```

打开活动列表。测试库包含学生 1（学号 S1）、学生 2（S2）和发布者 10；活动 1 可报名、2 已取消、3 已截止、4 无表单。冒烟脚本用正式 `/auth/login`（学号 S1/S2、工号 review，密码 `smoke123`）。测试脚本只用系统临时目录数据库，不读写 `backend/campus.db`。

启动开发服务后，可访问 `/tests/browser/index.html` 查看隔离的回归验证页。身份切换、错误开关、请求记录仅用于测试，不进入生产入口。详情测试按已实现后端返回 JSON，直接使用正式默认适配器；新增题目也使用正式拼音生成器。`frontend/demo/`、`backend/activities_stub.py`、`backend/seed_demo.py` 已清理。
