# AI Panel Studio — 项目架构说明

---

## 一、整体架构

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (React 18)               │
│  Vite + TypeScript + Zustand + React Router          │
│  localhost:5173                                      │
│                                                      │
│  pages/  →  business/  →  base/   (3-layer)         │
│  REST API client  +  SSE EventSource                │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP / SSE
                       │ /api/v1/*
┌──────────────────────▼──────────────────────────────┐
│                   Backend (FastAPI)                  │
│  Python 3.11 + uvicorn + aiosqlite                   │
│  localhost:8000                                      │
│                                                      │
│  routes/  →  services/  →  database   (3-layer)      │
│                      └─ llm.py (DeepSeek PRIVATE)    │
└──────────────────────┬──────────────────────────────┘
                       │ HTTPS
                       │ Bearer Token
┌──────────────────────▼──────────────────────────────┐
│              DeepSeek V4 Pro API                     │
│         api.deepseek.com/v1/chat/completions         │
│         (密钥仅在 config.py 环境变量中)                │
└─────────────────────────────────────────────────────┘
```

---

## 二、后端分层

```
backend/
├── main.py              ← FastAPI 入口、CORS、生命周期、全局异常处理
├── config.py            ← 环境变量统一加载（密钥唯一入口）
├── database.py          ← aiosqlite 连接管理 + 查询辅助
├── models.py            ← Pydantic 请求/响应/SSE Payload 模型
├── sse_manager.py       ← SSE 连接管理（按 discussion_id 隔离队列）
│
├── routes/              ← 【路由层】薄层，只做参数校验 + 调用 service
│   ├── discussions.py   ← /api/v1/discussions
│   ├── panelists.py     ← /api/v1/discussions/{id}/panelists
│   ├── streaming.py     ← /api/v1/discussions/{id}/stream (SSE)
│   └── summaries.py     ← /api/v1/discussions/{id}/summary
│
└── services/            ← 【业务逻辑层】路由不直接访问 DeepSeek
    ├── llm.py           ← ⚠ PRIVATE — 全部 LLM 调用 + Prompt 工程 + 内容过滤
    ├── discussions.py   ← 讨论 CRUD
    ├── panelists.py     ← 嘉宾管理 + AI 生成（含去重校验）
    ├── speeches.py      ← 发言编排（决策→流式生成→落库→SSE→共识分析）
    ├── consensus.py     ← 共识/分歧增删改 + SSE 广播
    └── summaries.py     ← 收尾总结生成 + 缓存
```

### 关键设计

| 约束 | 实现 |
|---|---|
| DeepSeek 密钥仅后端 | `config.py` 从 `DEEPSEEK_API_KEY` 环境变量加载；`services/llm.py` 私有函数 `_call_deepseek` / `_stream_deepseek`；路由层零 DeepSeek 引用 |
| 数据隔离 | 5 张表全部 `discussion_id` 索引；所有查询带 `WHERE discussion_id = ?`；SSE 按 discussion_id 维护独立客户端队列 |
| 内容过滤 | `_sanitize_content()` 清除 JSON/模型名/prompt 残留；`_validate_speech_length()` 截断过长发言；全局异常 handler 不泄露堆栈 |
| 并发生成锁 | `asyncio.Lock` + `_generating_flags` 字典，同一讨论同一时间仅一个发言生成中 |

---

## 三、前端分层

```
frontend/src/
├── main.tsx / App.tsx    ← 入口 + 路由
│
├── types/index.ts        ← 全部 TS 类型（对齐 api-contract.yaml）
├── api/client.ts         ← REST 客户端 + SSE EventSource（断线重连+补偿）
├── store/discussionStore.ts ← Zustand 全局讨论列表
├── styles/index.css      ← 暗色主题 + 动画 + 响应式
│
├── components/
│   ├── base/ (7)         ← 【基础通用层】零业务语义，可跨项目复用
│   │   ScrollPanel, ColorBadge, StatusIndicator, Modal,
│   │   SseStatusBar, HighlightText, ResponsiveShell
│   │
│   └── business/ (10)    ← 【业务 UI 层】只拼 base 组件 + api/client
│       DiscussionCard, NewDiscussionModal, PanelistWindow,
│       SpeechCard, SpeechTimeline, ConsensusList/Item,
│       DivergenceList/Item, StudioLayout
│
└── pages/ (2)            ← 【页面层】持有状态 + 排布 business 组件
    HomePage, StudioPage
```

### 关键设计

| 约束 | 实现 |
|---|---|
| 三栏独立滚动 | `ScrollPanel` 包裹每栏；body `overflow:hidden` |
| 演播厅沉浸式 | 深色主题 CSS 变量；`slideUp`/`highlightFade`/`ripple` 动画 |
| SSE 事件驱动 | `studioReducer` 分发 6 种 SSE 事件 → state 更新 → UI 自动刷新 |
| 多会话隔离 | `StudioPage` 用 `useReducer` 本地状态；路由离开即销毁；切换讨论时旧 SSE close → 新 SSE connect |
| 响应式三档 | `ResponsiveShell` + `useBreakpoint` Hook：≥1440px 三栏 / 768-1439px 双栏 / <768px 三 Tab |

---

## 四、数据模型

5 张核心表（SQLite，WAL 模式，9 个索引）：

```
discussions (1)
  ├── panelists (N)       ← discussion_id 外键 + 索引
  ├── speeches (N)        ← discussion_id + (discussion_id, sequence_num) 联合索引
  ├── consensus_points (N) ← discussion_id + (discussion_id, updated_at) 联合索引
  └── divergence_points (N) ← discussion_id + (discussion_id, updated_at) 联合索引
```

完整建表 SQL：`backend/init_db.sql`
ER 图：`api-contract.yaml` 内 Mermaid 图

---

## 五、SSE 事件流

```
GET /api/v1/discussions/{id}/stream
  │
  ├─ event: speech.chunk      ← 流式生成 token
  ├─ event: speech.complete   ← 完整发言落库
  ├─ event: consensus.update  ← 共识新增/更新
  ├─ event: divergence.update ← 分歧新增/更新/消解
  ├─ event: error             ← 生成/分析失败（不阻塞讨论）
  └─ event: heartbeat         ← 15s 无事件
```

---

## 六、技术选型

| 层 | 技术 | 选型理由 |
|---|---|---|
| 后端框架 | FastAPI (Python) | 原生 async/await、自动 OpenAPI 文档、SSE StreamingResponse 支持 |
| 数据库 | SQLite + aiosqlite | 零配置、WAL 模式支持读并发、单文件部署 |
| LLM SDK | httpx 直调 DeepSeek API | DeepSeek 兼容 OpenAI 协议，无额外 SDK 依赖 |
| 前端框架 | React 18 + TypeScript | 生态成熟、类型安全 |
| 构建工具 | Vite | 开发热更新快、生产构建小 |
| 状态管理 | Zustand（全局）+ useReducer（页面级） | 轻量、无 boilerplate、支持 Map 隔离模式 |
| SSE 客户端 | 原生 EventSource | 无需额外依赖，浏览器原生支持 |

---

## 七、后续迭代方向

### 短期（MVP 增强）
- [ ] 前端嘉宾生成 UI（目前需通过 Swagger 手动触发）
- [ ] 嘉宾头像 AI 生成（集成 DALL·E / Stable Diffusion）
- [ ] 讨论录音回放（按时间线重播 SSE 事件序列）
- [ ] 用户系统 + 讨论持久化到个人账户

### 中期（体验提升）
- [ ] 嘉宾发言音色 TTS（DeepSeek 文本转语音 + 不同嘉宾不同音色）
- [ ] 讨论过程导出（PDF / Markdown / 字幕文件）
- [ ] 讨论模板库（预设 10+ 种讨论场景：科技、商业、教育、政治…）
- [ ] 多语言支持（当前仅中文，扩展英文/日文界面）

### 长期（产品化）
- [ ] 实时观众互动（观众可投票、提问，AI 嘉宾实时回应）
- [ ] 多模型切换（支持 Claude、GPT、Gemini 作为备选 LLM）
- [ ] 讨论质量评分（AI 自动评估讨论深度、逻辑性、信息量）
- [ ] 企业私有化部署（Docker Compose 一键部署 + SSO 集成）
