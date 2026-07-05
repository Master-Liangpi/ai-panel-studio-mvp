# AI Panel Studio — 沉浸式 AI 圆桌演播厅

> 产品定位：用户创建圆桌讨论 → AI 自动生成嘉宾阵容 → 嘉宾持续自主辩论 → 共识分歧实时提取 → 讨论收尾总结。

全栈项目，前后端分离架构。DeepSeek V4 Pro 大模型密钥仅存于后端环境变量，前端不接触。

---

## 环境要求

| 组件 | 版本要求 | 说明 |
|---|---|---|
| Python | 3.11+ | 后端运行环境 |
| Node.js | 18+ | 前端构建环境 |
| DeepSeek API Key | — | 在 [DeepSeek 平台](https://platform.deepseek.com) 申请 |

---

## 快速开始（5 分钟）

### 1. 克隆项目

```bash
cd D:\AI圆桌讨论
```

### 2. 启动后端

```bash
cd backend

# 安装 Python 依赖
pip install -r requirements.txt

# 配置 DeepSeek API Key
cp .env.example .env
# 编辑 .env → 填入 DEEPSEEK_API_KEY=sk-xxxxxxxx

# 初始化数据库（首次自动创建 data/ai_panel_studio.db）
mkdir -p data

# 启动后端
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

验证：`curl http://localhost:8000/api/v1/health` → `{"status":"ok"}`

### 3. 启动前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

打开浏览器访问 `http://localhost:5173`

### 4. 走通全流程

1. 首页 → 点击「＋ 新建圆桌」→ 输入话题 → 创建
2. 进入演播厅 → 用 Swagger 生成嘉宾：`http://localhost:8000/docs` → `POST /api/v1/discussions/{id}/panelists/generate` → count=5
3. 刷新前端页面 → 嘉宾出现
4. 点击「🎤 下一轮发言」→ 观察打字机效果 → 共识/分歧面板实时刷新
5. 多次触发发言后 → 点击「📋 结束讨论并生成总结」

---

## 项目文档索引

| 文档 | 内容 | 角色 |
|---|---|---|
| `README.md` | 本文件：运行指南 | 所有人 |
| `ARCHITECTURE.md` | 项目架构说明 + 技术选型 + 迭代方向 | 开发者 |
| `api-contract.yaml` | OpenAPI 3.0 完整接口契约 | 前后端对接 |
| `integration-checklist.md` | 前后端联调校验清单（6 阶段 70+ 检查项） | QA / 联调 |
| `e2e-test-script.md` | E2E 人工自测脚本（5 组测试 60 步） | QA / 验收 |
| `test-specifications.md` | TDD 测试用例规格（70 个场景伪代码） | 开发者 |
| `e2e-acceptance-plan.md` | E2E 验收方案（全流程 + 专项 + 签核） | PM / QA |
| `frontend-architecture.md` | 前端设计稿（组件分层 + 布局 + 状态管理） | 前端开发者 |
| `GIT_GUIDE.md` | Git 提交规范 | 开发者 |
| `DEMO_DATA.md` | 5 组预设样例数据 | 演示 / 开箱即用 |
| `PROJECT_INDEX.md` | 完整目录结构清单 | 交付归档 |
| `backend/README.md` | 后端专属启动文档 | 后端开发者 |
| `frontend/README.md` | 前端专属启动文档 | 前端开发者 |
