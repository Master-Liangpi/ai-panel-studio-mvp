# AI Panel Studio — 后端服务

AI 圆桌演播厅后端，基于 FastAPI + SQLite + DeepSeek V4 Pro。

---

## 快速启动

### 1. 环境准备

```bash
# Python 3.11+ 推荐
python --version

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 复制模板
cp .env.example .env

# 编辑 .env，填入 DeepSeek API Key（必填）
# DEEPSEEK_API_KEY=sk-your-actual-key
```

### 3. 初始化数据库

数据库会在首次启动时自动创建（`data/ai_panel_studio.db`）。

如需手动初始化：

```bash
mkdir -p data
sqlite3 data/ai_panel_studio.db < init_db.sql
```

### 4. 启动服务

```bash
# 开发模式（热重载）
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 或直接运行
python main.py
```

### 5. 验证

```bash
# 健康检查
curl http://localhost:8000/api/v1/health

# API 文档（Swagger）
open http://localhost:8000/docs
```

---

## 项目结构

```
backend/
├── main.py                  # FastAPI 入口，CORS，生命周期
├── config.py                # 环境变量统一管理（密钥只在此加载）
├── database.py              # SQLite 连接 + 查询辅助
├── models.py                # Pydantic 请求/响应模型
├── sse_manager.py           # SSE 连接管理（按 discussion_id 隔离）
├── init_db.sql              # 数据库建表脚本
├── .env.example             # 环境变量模板
├── requirements.txt         # Python 依赖
├── README.md                # 本文件
│
├── services/                # 业务逻辑层
│   ├── llm.py               # DeepSeek 调用（PRIVATE — 路由不直接访问）
│   ├── discussions.py       # 讨论 CRUD
│   ├── panelists.py         # 嘉宾管理 + AI 生成
│   ├── speeches.py          # 发言调度 + 流式生成编排
│   ├── consensus.py         # 共识/分歧提取 + SSE 推送
│   └── summaries.py         # 收尾总结生成
│
└── routes/                  # API 路由层（薄层，只做参数校验 + 调用 service）
    ├── discussions.py       # /api/v1/discussions
    ├── panelists.py         # /api/v1/discussions/{id}/panelists
    ├── streaming.py         # /api/v1/discussions/{id}/stream (SSE)
    └── summaries.py         # /api/v1/discussions/{id}/summary
```

---

## API 端点速查

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/v1/discussions` | 新建讨论 |
| `GET` | `/api/v1/discussions` | 讨论列表 |
| `GET` | `/api/v1/discussions/{id}` | 讨论详情 |
| `PATCH` | `/api/v1/discussions/{id}` | 更新讨论 |
| `DELETE` | `/api/v1/discussions/{id}` | 删除讨论（级联） |
| `POST` | `/api/v1/discussions/{id}/panelists/generate` | AI 生成嘉宾 |
| `GET` | `/api/v1/discussions/{id}/panelists` | 嘉宾列表 |
| `POST` | `/api/v1/discussions/{id}/panelists` | 手动添加嘉宾 |
| `PATCH` | `/api/v1/discussions/{id}/panelists/{pid}` | 修改嘉宾 |
| `DELETE` | `/api/v1/discussions/{id}/panelists/{pid}` | 移除嘉宾 |
| `GET` | `/api/v1/discussions/{id}/stream` | **SSE 实时推送** |
| `GET` | `/api/v1/discussions/{id}/speeches` | 发言列表 |
| `POST` | `/api/v1/discussions/{id}/speeches/next` | **触发 AI 发言** |
| `GET` | `/api/v1/discussions/{id}/consensus` | 共识列表 |
| `GET` | `/api/v1/discussions/{id}/divergence` | 分歧列表 |
| `POST` | `/api/v1/discussions/{id}/summary` | 生成总结 |
| `GET` | `/api/v1/discussions/{id}/summary` | 查看总结 |
| `GET` | `/api/v1/health` | 健康检查 |

完整接口文档：http://localhost:8000/docs

---

## 核心架构约束

### DeepSeek 密钥隔离
- 密钥**仅**通过环境变量 `DEEPSEEK_API_KEY` 读入，加载于 `config.py`
- 所有 LLM 调用封装在 `services/llm.py`，路由层不直接 import DeepSeek 相关逻辑
- 前端通过 REST/SSE 间接使用 AI 能力，**绝对不直连大模型**

### 数据隔离
- 所有子表查询带 `WHERE discussion_id = ?`，由路由层传入
- 多场讨论同时运行时数据库互不干扰
- 5 张核心表全部 `discussion_id` 已建索引

### SSE 推送
- `sse_manager.py` 按 discussion_id 维护客户端队列
- 发言 chunk / 完整发言 / 共识更新 / 分歧更新分四种 `event:` 类型推送
- 15 秒无业务事件自动发送心跳
- 断线重连传 `?after_sequence=` 参数补偿遗漏数据

### 内容隐藏
- `services/llm.py` 中 `_sanitize_content()` 和 `_validate_speech_length()` 过滤模型内部输出
- 全局异常处理器不向前端返回详细堆栈（debug 模式除外）
- 所有 prompt 模版中的内部标记（如 `reason` 字段）仅在后端日志中出现

---

## 环境变量参考

| 变量 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `DEEPSEEK_API_KEY` | **是** | — | DeepSeek API 密钥 |
| `DEEPSEEK_BASE_URL` | 否 | `https://api.deepseek.com` | API 地址 |
| `DEEPSEEK_MODEL` | 否 | `deepseek-chat` | 模型名称 |
| `DATABASE_PATH` | 否 | `./data/ai_panel_studio.db` | SQLite 文件路径 |
| `SERVER_HOST` | 否 | `0.0.0.0` | 监听地址 |
| `SERVER_PORT` | 否 | `8000` | 监听端口 |
| `LOG_LEVEL` | 否 | `info` | 日志级别 |
| `SSE_HEARTBEAT_INTERVAL` | 否 | `15` | SSE 心跳间隔（秒） |
| `DEEPSEEK_TIMEOUT` | 否 | `60` | API 超时（秒） |
| `DEEPSEEK_STREAM_TIMEOUT` | 否 | `120` | 流式 API 超时（秒） |
