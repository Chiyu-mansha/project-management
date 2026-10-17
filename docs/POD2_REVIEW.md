# POD-2 统筹修改 review 索引

日期：2026-10-17。分支：`codex/pod2-integration-review`；基线：`2219c8b`。

## 先 review 这些改动

| 文件 | 改动与原因 |
| --- | --- |
| frontend/src/api/request.js、registrations.js | 仅 getActivity 显式兼容 POD-1 的裸活动 JSON，修复新建模板/打开报名读取活动失败；报名八接口仍严格验壳 |
| frontend/vite.config.js | 代理改为 127.0.0.1，落实第二讨论区报告的 Windows IPv6/IPv4 连接问题 |
| backend/db.py | 为事务增加可选 BEGIN IMMEDIATE，允许调用方在校验前取得写锁 |
| backend/registrations.py | 报名名额/状态/重复检查与写入同事务；取消的凭证检查与删除同事务；两个列表限制分页范围；保持容量单位为队伍数 |
| backend/forms.py | 创建表单与“已有报名不可修改”的检查、写入放进同一事务，避免与并发报名交错 |
| backend/common.py | 正确解析带时区、小数秒及 Z 的截止时间；无效日期拒绝，不能默认为尚未截止 |
| backend/schemas.py | 文本答案严格为字符串；固定学号/姓名题干与前端相同，防止服务端保存后前端无法加载 |
| backend/tests/test_registration_integration.py | 8 项真实 HTTP/SQLite 回归；只用临时数据库 |
| frontend/tests/contracts.test.mjs | 新增活动详情适配与拒绝错误的回归测试，总计 23 项 |
| docs/POD2_API.md | 根据仓库实际模型和返回值补齐八接口 JSON、权限、校验与状态码 |
| docs/POD2_HANDOFF.md、frontend/INTEGRATION.md | 列出现有六个组件入口、事件、POD-1 接线要求和消息/讨论区回复草稿 |
| docs/POD2_WEEKLY_2026-10-17.md | 周报草稿，区分本次完成项和仍需接入的工作 |
| README.md、backend/requirements-dev.txt | 增加 review 入口和测试复现方式；修正文档中的 schema 版本/表数 |

没有新增报名路由或数据库表，没有改写 POD-1/POD-3 的业务表结构，也没有往活动页注入假会话。

## 合并状态核对

拉取时 origin/main 与 origin/pod2/00-student-participation 同为 2219c8b，已有成员代码与两次后续修正均在该集成基线内。因此没有重复合并旧成员分支；本次修复独立放到 review 分支，目标为 POD-2 集成分支。

## 已执行验证

- 后端：8 项 unittest 接口回归通过，约 1 秒；真实 FastAPI HTTP 调用与临时 SQLite。
- 前端：23 项 Node 测试通过。
- 前端：Vite 生产构建通过；构建仍提示既有大 chunk，未为本次联调额外拆包。
- git diff --check 通过。

后端场景包括八接口完整流程、队员取消被拒、整队任一队员有凭证/签到被拒、级联删除、重复成员、越权、cancelled 历史保留、分页边界、时区截止时间和一队名额并发提交。

本次机器的 Windows 沙箱阻止 asyncio socketpair，最小 TestClient 示例也会卡住；在正常执行环境运行同一套测试后通过。未用绕过断言或跳过测试处理此问题。

## 尚未完成/需要共同 review

1. 正式登录域未接入 RegistrationEntry，POD-1 活动页尚未绑定报名/模板/名单按钮。代码单模块通过不代表真实登录页面已完成端到端联调。
2. 推荐/画像路径与 AI 打分契约在 HANDOFF 中是明确标注的提案。AI 打分名称、结果语义和存储迁移须 PM/技术负责人/POD-1 确认；本次未伪造评分或新建表。
3. POD-1 活动详情最终是否统一响应外壳由其负责人协调；本次仅在调用边界兼容。
4. 凭证域后续发证时仍须在自己的事务中核对报名存在，不能依据旧快照给已经取消的报名发证。
5. POD-1 消息、讨论区回复、周报先保留为草稿，待本次 review 后正式提交。

## 对原八项任务的对应

| 原任务 | 本次产出/状态 |
| --- | --- |
| 看两个讨论区 | 已读取正文及 PM/POD-2/TA 后续回复，按最终结论执行 |
| 看周报定当周功能 | 已读取 POD2 第二周周报，优先报名模块与 POD-1 联调 |
| 补模块接口文档 | API 文档已补齐并对照代码；HTTP 200/400/401/403/404/409 沿用实现 |
| 交接 POD-1 函数与 JSON | 已整理真实入口和事件、消息草稿；正式父页面接线未完成 |
| 新接口/表找组长确认 | 推荐等新增契约已列具体提案；未擅自新增表或宣称获批 |
| 回复讨论内容 | 已写两份针对具体结论的回复草稿；未发送 |
| 交周报 | 已写本次周报草稿；未正式提交 |
| 合并检查/提交 POD-2 分支 | 已核对集成基线、完成修复与测试；通过独立 review 分支提交审阅，不直接覆盖共享分支 |
