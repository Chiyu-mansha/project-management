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

打开 http://localhost:5173 查看报名模块入口。POD-2 报名前端按文档提供弹窗和列表组件，由 POD-1 的活动页面传入活动 ID、由认证域传入登录状态，接入方式见 [frontend/INTEGRATION.md](frontend/INTEGRATION.md)。当前后端仍只有 `/api/hello`，报名业务接口尚需后端成员提供。

前端校验：`npm test`；生产构建：`npm run build`。

## 目录结构

```
backend/
  main.py          # FastAPI 入口(含 CORS、/api/hello)
  schema.sql       # 五张核心表建表语句
  requirements.txt
frontend/
  src/App.vue      # 入口页面
  src/api/         # 文档约定的报名请求与 Bearer token
  src/domain/      # POD-2 报名组件及供 POD-1 调用的函数
```

## 分支规则

- 每个人在自己的 `podN/member-X` 分支开发
- 提 PR 合到本 POD 的 `podN/00-xxx` 合并分支
- 每周由组长把合并分支合入 `main`

## AI 能力

统一走 AI 网关(技术负责人封装),各 POD 只调网关、不直连大模型。Key 放本地 `.env`,禁止提交仓库(见 backend/.env.example)。
