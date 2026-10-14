# POD-2 报名前端对接

依据用户提供的报名文档第 3、7 节，以及 2026-10-11 定稿的通用约定和报名域。本次只实现报名域前端，不实现后端、认证界面、POD-1 活动发布/活动列表/推文界面、画像、推荐或待定的 Excel 导出。

## 已执行的约定

- 8 个报名接口的路径、方法保持不变。POST/PUT JSON 使用报名文档第 7 节的字段。
- 最新成功响应为 `{ "code": 0, "data": ... }`；错误为 `{ "code": 4xx/5xx, "message": "..." }`。早期 `code:200/msg` 已被定稿覆盖。
- 每次请求携带 `Authorization: Bearer <token>`。会话由登录域传入，不约定 localStorage 键名。
- 列表携带 `page/page_size`。兼容已提供的两种列表数据：报名第 7 节的 `data: []` 与最新分页的 `data: { items, total }`；不会接受猜测的其他结构。
- 新建模板只读调用已定稿的 POD-1 `GET /api/activities/{id}`，读取人数；学生打开报名时也检查活动是否已取消。活动截止字段沿用 `signup_deadline`，本模块没有重新定义或提交该字段。
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

也可使用 `home` 作用域插槽装入 POD-1 的原页面。打开列表时隐藏该插槽，返回时恢复，未新增约定外的路由或活动编辑页面。

根 `App.vue` 目前只挂载报名组件，没有虚构会话、活动数据或登录页面。没有 POD-1 入口和登录状态时不会展示假的已登录功能。

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

开发 `/api` 代理到 `http://localhost:8000`；可用 `.env.example` 配置前端 API base。合并分支已实现 8 个报名接口。活动详情 `GET /api/activities/{id}` 由 POD-1 提供；本次已清理临时活动只读桩及其入口注册，单独运行 POD-2 后端时不再提供这个活动域接口。

启动开发服务后，可访问 `/tests/browser/index.html` 查看隔离的回归验证页。身份切换、错误开关、请求记录仅用于测试，不进入生产入口。详情测试按已实现后端返回 JSON，直接使用正式默认适配器；新增题目也使用正式拼音生成器。`frontend/demo/`、`backend/activities_stub.py`、`backend/seed_demo.py` 已清理。
