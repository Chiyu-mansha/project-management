# 陈珑珑本周前端交付（2026-10-17）

分支 `pod2/member-2`，继续使用 [PR #6](https://github.com/Chiyu-mansha/project-management/pull/6)，目标 `pod2/00-student-participation`。已先合入现有 main，解决个人分支与集成分支的重复提交冲突，沿用集成分支已有拼音字段生成和详情适配。本次功能差异全部在 frontend；没有新增后端接口或数据库表。

## 建议 review 顺序

1. `src/domain/ActivityRegistrationActions.vue`：活动发布者的表单/名单入口，学生报名和我的报名，截止和五态禁用提示，成功事件带活动 ID。
2. `src/auth/session.js`、`src/views/RegistrationEntry.vue`：共享会话、本人报名列表自动加载；登录模块通过 setSession 接入。
3. `src/domain/RegistrationDomain.vue` 及三个弹窗：401 通知、切换身份/活动/页面时清理旧状态、请求取消和旧结果丢弃；失败保留填写内容，成功才关闭/刷新。
4. `src/api/request.js`、`src/api/registrations.js`：报名 API 严格 code/data，只有 POD-1 活动只读请求兼容裸 JSON；HTTP/业务失败继续抛错。
5. `src/views/ActivityDetail.vue`、`ActivityList.vue`：挂载报名入口，统一 API base 和开发代理，支持活动响应新旧格式；加载失败可见、路由变化不显示旧活动。
6. `src/auth/DevSessionPanel.vue`：仅开发环境通过已有 /api/dev/token 取凭证；生产构建不含此入口。

## 验证

- `npm test`：27 项通过，包含原表单契约及新增会话、权限、五态/截止、响应兼容与旧会话 401 回归。
- `npm run build`：通过；沿用项目现有的大 chunk 提示。已检查产物不含开发联调登录、dev/token 和测试种子标记。
- `node tests/live-api-smoke.mjs`：使用 tests/serve-backend.py 的临时 SQLite，真实调用全部八个报名接口、POD-1 活动详情及已有开发 token 接口；重复报名 409、已有报名修改模板 400、队员取消 403、队长取消后整队记录清理、取消/截止拒绝均通过。
- 浏览器：学生登录→活动页填写→报名成功→我的报名→真实详情；重复提交显示“该成员已报名本活动”且保留输入；截止/取消活动报名按钮禁用；发布者查看模板、已有报名时编辑被锁定；活动列表通过统一代理加载。

运行方法和六个函数交接见 [INTEGRATION.md](INTEGRATION.md)。截图由本次 review 单独提供，不将用户数据或生成的数据库加入仓库。

## 交付边界

当前后端没有正式密码登录 API，因此正式认证接入点已提供，真实页面联调用仓库已有开发 token 完成，不宣称正式登录上线。画像/推荐/AI 评分按本周清单交付 [字段和状态设计](SCORING_CONTRACT.md)，不将尚未实现的后端契约当成已可调用服务。本次测试针对仓库现有 POD-1/POD-2 代码与临时测试数据，不代替与其他成员部署环境的最终联合验收。
