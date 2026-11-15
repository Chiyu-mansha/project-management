# POD-3 第一周交付包：凭证管理

本目录对应项目文档中的 POD-3 业务链路：

`签到核销 -> 自动发放电子活动票 -> 名单确认 -> 电子签章 -> 凭证仓库 -> 导出`

## 第一周目标对齐

项目进度看板把第一周目标定义为环境准备、API 契约 v1.0 和数据库 schema v1.0。POD-3 本周交付物如下：

- `docs/POD3_WEEK1_SPEC.md`：范围、流程、状态机、权限、验收标准和联调约定。
- `api/pod3-openapi.yaml`：REST API 契约 v1.0，可供前后端并行开发。
- `db/pod3-schema.sql`：PostgreSQL 数据库 schema v1.0。
- `db/pod3-seed.sql`：用于联调的最小演示数据。
- `mock/server.py`：不依赖第三方包的 Mock API。
- `tests/test_mock_api.py`：核心链路自动化冒烟测试。

## 快速运行

要求：Python 3.10+。

```bash
cd pod3-week1
python3 mock/server.py --port 8088
```

健康检查：

```bash
curl http://127.0.0.1:8088/health
```

运行测试：

```bash
cd pod3-week1
python3 -m unittest discover -s tests -v
```

## 核心接口

POD-3 规定的正式接口使用 `/api` 前缀：

- `POST /api/activities/{id}/checkin`：签到核销并自动发放电子活动票。
- `GET /api/activities/{id}/checkin-list`：负责人查看签到名单。
- `POST /api/activities/{id}/confirm`：负责人确认签到名单。
- `POST /api/credentials/{id}/sign`：对单张凭证进行电子签章。
- `GET /api/credentials`：当前登录学生的凭证仓库，身份从 JWT 获取。
- `GET /api/credentials/{id}/pdf`：获取已签章凭证 PDF 的临时下载信息。
- `GET /api/credentials/export`：学生导出个人凭证；负责人携带 `activity_id` 批量导出活动名单。

`/api/v1` 下的旧路径暂时保留用于兼容已开始联调的客户端，新增开发应只使用上面的正式接口。

## 技术假设

- 接口风格：REST + JSON，统一前缀 `/api/v1`。
- 数据库：PostgreSQL 15+，ID 使用 UUID，时间统一保存为 UTC。
- 身份认证：团队统一 JWT；凭证仓库使用 JWT 的 `sub` 作为当前学生身份，负责人名单和导出使用 JWT 角色与组织权限。
- Mock 联调时用 `X-Demo-User-Id` 模拟 JWT 的 `sub`，用 `X-Demo-Role: ORGANIZER` 模拟负责人角色；正式服务必须替换为真实 JWT 中间件。
- 活动、学生和组织由其他模块维护，POD-3 仅保存其 ID，避免跨模块强外键耦合。
- 真实签章、对象存储和 PDF 生成由后续适配器接入；第一周先冻结契约和数据结构。

## 第一周完成定义（DoD）

- [x] POD-3 范围与非范围明确。
- [x] 主流程、异常流程和状态机明确。
- [x] API v1.0 可供前后端评审与联调。
- [x] schema v1.0 包含唯一约束、索引、审计与幂等字段。
- [x] Mock API 可运行。
- [x] 签到发放电子活动票、名单确认签章、仓库查询、导出链路有自动化冒烟测试。
- [ ] 团队确认实际技术栈、统一错误码和 JWT 字段后，将本包合入主仓库。
