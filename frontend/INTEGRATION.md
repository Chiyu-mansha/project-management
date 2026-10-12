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
    :generate-field-key="agreedFieldKeyGenerator"
    :read-registration-detail="agreedRegistrationDetailReader"
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

## 文档尚未提供的两项

### 中文题干到英文 field_key 的规则

文档要求“根据 label 转英文、前端自动生成、用户不可编辑”，但没有规定转换方法。本次不自行用序号、拼音、UUID 或翻译 API替代。

`generateFieldKey(label)` 接收题干，返回英文 key（可返回 Promise）。收到团队确认的生成规则后在该函数中实现即可。已有题目使用原 key；新题目无规则时阻止提交，并保持弹窗和题目草稿。固定学号姓名不依赖此规则。

### GET /api/registrations/{id} 的完整响应 JSON

已给文档只指定详情路径和用途，没有完整 JSON；没有猜测它包含 `activity_id`、schema 或 `extra_fields` 的具体嵌套位置。

详情请求和弹窗已实现。`readRegistrationDetail(data, { record, signal })` 由最终响应契约对应的适配函数提供；其输出是以下**前端内部展示数据**，不是新增后端 JSON 契约：

```js
{
  teamSchema,       // 模板的 form_team_schema
  memberSchema,    // 模板的 form_member_schema
  teamExtra,       // 报名中的队伍答案
  members,         // 文档定义的 role/member_extra 成员列表
  isIndividual     // 活动 min/max 均为 1
}
```

取消按钮依据“我的报名”接口中已定义的 `my_role` 显示，不通过详情猜测当前身份。缺少适配函数时不能展示详情或取消，错误不会导致弹窗关闭。

## 本地验证

```powershell
cd frontend
npm install
npm test
npm run build
npm run dev
```

开发 `/api` 代理到 `http://localhost:8000`；可用 `.env.example` 配置前端 API base。当前仓库后端只实现 `/api/hello`，8 个报名接口需要后端成员提供，不能据此声称已完成真实联调。

启动开发服务后，可访问 `/tests/browser/index.html` 查看隔离的文档样例验证页。这里的身份切换、错误开关、请求记录仅用于测试，不进入生产入口。测试只使用已提供的表单和报名样例；详情测试返回 `data:null` 并用显式测试适配函数读取内存样例，不把未定稿的响应 JSON 当成契约。
