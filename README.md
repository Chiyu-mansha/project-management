# 校园活动智能通知&报名助理

## 技术栈

- 前端:Vue 3 + Vite + Element Plus
- 后端:Python FastAPI
- 数据库:SQLite(MVP)
- 认证:统一认证域提供的简单 token,POD-3 不签发或解析 JWT

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

打开 http://localhost:5173,点「检测后端连接」按钮,显示"已连通"即最简链路打通 ✅

## 目录结构

```
backend/
  main.py          # FastAPI 入口(含 CORS、/api/hello)
  schema.sql       # 全组共享 SQLite schema
  pod3_schema.sql  # POD-3 自有流程表(schema 不创建 users/activities)
  requirements.txt
frontend/
  src/App.vue      # 入口页面(内置后端连通检测)
```

## 分支规则

- 每个人在自己的 `podN/member-X` 分支开发
- 提 PR 合到本 POD 的 `podN/00-xxx` 合并分支
- 每周由组长把合并分支合入 `main`

## POD-3 联调配置

- `POD3_DB_PATH` 指向全组共享 SQLite 数据库,默认是 `campus.db`。
- `AUTH_SERVICE_URL` 配置认证域地址。请求中的 Bearer 值是简单 token,由认证域校验。
- `ACTIVITY_SERVICE_URL` 配置活动域地址;未配置时只从共享 SQLite 的 `activities` 表读取。
- POD-3 不创建或写入 `users`、`activities` 表,只写凭证域及其流程表。

## AI 能力

统一走 AI 网关(技术负责人封装),各 POD 只调网关、不直连大模型。Key 放本地 `.env`,禁止提交仓库(见 backend/.env.example)。
