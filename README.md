# 校园活动智能通知&报名助理

## 技术栈

- 前端:Vue 3 + Vite + Element Plus
- 后端:Python FastAPI
- 数据库:SQLite(MVP)

## 快速开始

### 后端

```bash
cd backend
python3 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

浏览器打开 http://localhost:8000/api/hello 看到 JSON 即成功。

### 前端

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173 查看报名模块入口。活动页传入活动 ID，认证域传入登录状态，接入方法见 [frontend/INTEGRATION.md](frontend/INTEGRATION.md)。新增题目自带拼音 key 生成，报名详情自带后端响应适配。

前端验证：`npm test`；生产构建：`npm run build`。活动详情接口由 POD-1 提供，演示页、临时活动桩及演示种子脚本已清理。

## 目录结构

```
backend/
  main.py          # FastAPI 入口(POD-1/2/3 路由)
  schema.sql       # 全组共享 SQLite schema v1.5
  pod3_schema.sql  # POD-3 仅补 credentials 唯一索引，不重建共享表
  credentials.py   # 签到 / 确认 / 签章 / 凭证仓库
  requirements.txt
frontend/
  src/views/Credentials.vue     # 学生凭证页
  src/views/CheckinManage.vue   # 发布者签到核销
  src/domain/                   # POD-2 报名组件
```

## POD-3 第 5 周（进 main）

- 使用共享认证：`Authorization: Bearer student:<id>` / `organizer:<id>`。
- 签到前必须已在 `registration_members` 中报名。
- 凭证写入 schema v1.5 的 `credentials` 表：`issued → confirmed → signed`。
- 学生页：`/credentials`；活动详情可签到；发布者在活动详情进入 `/activities/:id/checkins`。

## 分支规则

- 每个人在自己的 `podN/member-X` 分支开发
- 提 PR 合到本 POD 的 `podN/00-xxx` 合并分支
- 每周由组长把合并分支合入 `main`

## AI 能力

统一走 AI 网关(技术负责人封装),各 POD 只调网关、不直连大模型。Key 放本地 `.env`,禁止提交仓库(见 backend/.env.example)。
