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
  main.py          # FastAPI 入口(含 CORS、/api/hello)
  schema.sql       # 五张核心表建表语句
  requirements.txt
frontend/
  src/App.vue      # 报名模块入口
  src/domain/      # POD-2 报名组件、拼音 key 生成及详情适配
```

## 分支规则

- 每个人在自己的 `podN/member-X` 分支开发
- 提 PR 合到本 POD 的 `podN/00-xxx` 合并分支
- 每周由组长把合并分支合入 `main`

## AI 能力

统一走 AI 网关(技术负责人封装),各 POD 只调网关、不直连大模型。Key 放本地 `.env`,禁止提交仓库(见 backend/.env.example)。
