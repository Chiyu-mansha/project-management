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
  schema.sql       # 十张表建表语句(与飞书《数据库 Schema v1.3》一致)
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

## POD-2 联调 review（2026-10-17）

- [改动清单与验证结果](docs/POD2_REVIEW.md)
- [八个报名接口的 JSON、校验与状态码](docs/POD2_API.md)
- [POD-1 真实入口函数与待确认提案](docs/POD2_HANDOFF.md)
- [周报草稿](docs/POD2_WEEKLY_2026-10-17.md)

后端回归使用临时 SQLite，不读取或清空业务库：安装 `backend/requirements-dev.txt` 后在仓库根目录运行 `python -m unittest discover -s backend/tests -v`。前端运行 `npm test` 与 `npm run build`。Windows 沙箱若阻止 asyncio 的本地 socketpair，需要在正常终端运行后端 HTTP 测试。
