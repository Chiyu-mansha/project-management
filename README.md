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

浏览器打开 http://localhost:8000/health 看到 JSON 即成功。

POD-3 正式服务接口使用 `/api` 前缀。开发环境可以先获取 JWT：

```bash
curl -X POST http://localhost:8000/api/auth/dev-token \
  -H 'Content-Type: application/json' \
  -d '{"subject":"00000000-0000-4000-8000-000000000001","roles":["STUDENT"]}'
```

生产环境必须关闭开发 Token 接口，并把 `JWT_SECRET` 放入密钥管理服务。

### 前端

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173,点「检测后端连接」按钮,显示"已连通"即最简链路打通 ✅

## 目录结构

```
backend/
  main.py          # POD-3 正式 FastAPI 接口、JWT 权限和业务流程
  auth.py          # HS256 JWT 校验与角色依赖
  database.py      # SQLite 持久化适配器
  integrations.py  # 活动/用户模块 HTTP 适配器
  storage.py       # PDF、文件存储和电子签章适配器
  pod3_schema.sql  # POD-3 MVP 数据库表结构
  schema.sql       # 五张核心表建表语句
  requirements.txt
frontend/
  src/App.vue      # 入口页面(内置后端连通检测)
```

## 分支规则

- 每个人在自己的 `podN/member-X` 分支开发
- 提 PR 合到本 POD 的 `podN/00-xxx` 合并分支
- 每周由组长把合并分支合入 `main`

## POD-3 正式接口

- `POST /api/activities/{id}/checkin`
- `GET /api/activities/{id}/checkin-list`
- `POST /api/activities/{id}/confirm`
- `POST /api/credentials/{id}/sign`
- `GET /api/credentials`
- `GET /api/credentials/{id}/pdf`
- `GET /api/credentials/export`

默认使用 SQLite 和本地 `backend/storage/` 作为 MVP 适配器；配置
`ACTIVITY_SERVICE_URL`、`USER_SERVICE_URL`、`SEAL_SERVICE_URL` 后，会分别调用活动、用户和签章服务。

## AI 能力

统一走 AI 网关(技术负责人封装),各 POD 只调网关、不直连大模型。Key 放本地 `.env`,禁止提交仓库(见 backend/.env.example)。
