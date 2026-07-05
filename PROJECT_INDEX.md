# AI Panel Studio — 项目文件清单

> 完整可交付物目录，共 **50 个文件**，分 5 大类。

---

## 一、设计文档（6 个）

```
D:\AI圆桌讨论\
├── api-contract.yaml            # OpenAPI 3.0 接口契约（15 端点 + SSE 6 事件）
├── frontend-architecture.md     # 前端设计稿（3 层 17 组件 + 布局 + 状态管理）
├── test-specifications.md       # TDD 测试规格（70 个用例伪代码）
├── e2e-acceptance-plan.md       # E2E 验收方案（5 阶段 + 4 专项 + 签核清单）
├── integration-checklist.md     # 前后端联调校验清单（70+ 检查项）
└── e2e-test-script.md           # E2E 人工自测脚本（5 组测试 60 步）
```

## 二、交付文档（5 个）

```
D:\AI圆桌讨论\
├── README.md                    # 项目总 README（运行指南 + 文档索引）
├── ARCHITECTURE.md              # 项目架构说明（分层 + 技术选型 + 迭代方向）
├── GIT_GUIDE.md                 # Git 提交规范
├── DEMO_DATA.md                 # 5 组预设样例演示数据
└── PROJECT_INDEX.md             # 本文件：完整目录结构清单
```

## 三、后端代码（20 个）

```
D:\AI圆桌讨论\backend\
├── .env.example                 # 环境变量模板
├── requirements.txt             # Python 依赖（6 个包）
├── README.md                    # 后端启动文档
├── init_db.sql                  # SQLite 建表脚本（5 表 9 索引）
│
├── main.py                      # FastAPI 入口：CORS、生命周期、异常处理
├── config.py                    # 环境变量管理（密钥唯一加载点）
├── database.py                  # aiosqlite 连接 + 查询辅助
├── models.py                    # Pydantic 请求/响应/SSE 模型
├── sse_manager.py               # SSE 连接管理（按 discussion_id 隔离）
│
├── services/                    # 业务逻辑层
│   ├── __init__.py
│   ├── llm.py                   # ⚠ DeepSeek 全部调用 + Prompt 工程 + 内容过滤
│   ├── discussions.py           # 讨论 CRUD
│   ├── panelists.py             # 嘉宾管理 + AI 生成（含去重后置校验）
│   ├── speeches.py              # 发言编排：决策→流式→落库→SSE→共识分析
│   ├── consensus.py             # 共识/分歧增删改 + SSE 广播
│   └── summaries.py             # 收尾总结生成 + 缓存
│
└── routes/                      # API 路由层（薄层）
    ├── __init__.py
    ├── discussions.py           # /api/v1/discussions
    ├── panelists.py             # /api/v1/discussions/{id}/panelists
    ├── streaming.py             # /api/v1/discussions/{id}/stream (SSE) + speeches
    └── summaries.py             # /api/v1/discussions/{id}/summary
```

## 四、前端代码（19 个）

```
D:\AI圆桌讨论\frontend\
├── .env.example                 # 前端环境变量模板
├── index.html                   # HTML 入口
├── package.json                 # Node 依赖（React 18 + Vite + Zustand）
├── vite.config.ts               # Vite 配置（含 API 代理）
├── tsconfig.json                # TypeScript 配置
├── README.md                    # 前端启动文档
│
└── src/
    ├── main.tsx                  # 入口
    ├── App.tsx                   # 路由 + ResponsiveShell
    │
    ├── types/index.ts            # TypeScript 类型定义
    ├── api/client.ts             # REST 客户端 + SSE EventSource
    ├── store/discussionStore.ts  # Zustand 全局状态
    ├── styles/index.css          # 全局样式（暗色主题 + 动画 + 响应式）
    │
    ├── components/
    │   ├── base/ (7)             # 基础通用组件
    │   │   ├── ScrollPanel.tsx
    │   │   ├── ColorBadge.tsx
    │   │   ├── StatusIndicator.tsx
    │   │   ├── Modal.tsx
    │   │   ├── SseStatusBar.tsx
    │   │   ├── HighlightText.tsx
    │   │   └── ResponsiveShell.tsx
    │   │
    │   └── business/ (10)        # 业务 UI 组件
    │       ├── DiscussionCard.tsx
    │       ├── NewDiscussionModal.tsx
    │       ├── PanelistWindow.tsx
    │       ├── SpeechCard.tsx
    │       ├── SpeechTimeline.tsx
    │       ├── ConsensusList.tsx
    │       ├── ConsensusItem.tsx
    │       ├── DivergenceList.tsx
    │       ├── DivergenceItem.tsx
    │       └── StudioLayout.tsx
    │
    └── pages/ (2)                # 页面组件
        ├── HomePage.tsx
        └── StudioPage.tsx
```

## 五、文件统计

| 类别 | 数量 | 格式 |
|---|---|---|
| 设计文档 | 6 | `.md` × 5 + `.yaml` × 1 |
| 交付文档 | 5 | `.md` × 5 |
| 后端代码 | 20 | `.py` × 15 + `.sql` × 1 + `.txt` × 1 + `.md` × 1 + `.example` × 1 |
| 前端代码 | 19 | `.tsx` × 14 + `.ts` × 2 + `.css` × 1 + `.json` × 1 + `.html` × 1 |
| **合计** | **50** | |

---

## 六、交付打包命令

```bash
# 在 D:\AI圆桌讨论 目录下

# 方式 1：直接用压缩工具打包整个目录
# 注意排除 node_modules、__pycache__、.venv、*.db
# Windows: 右键 → 发送到 → 压缩文件夹（手动删除上述目录）
# 或使用 PowerShell:
Compress-Archive -Path * -DestinationPath AI-Panel-Studio.zip

# 方式 2：使用 Git 归档（推荐）
git init
git add -A
git commit -m "chore: 项目完整交付"
git archive --format=zip --output=AI-Panel-Studio.zip HEAD
```

### 排除清单（打包时应排除）

```
node_modules/
__pycache__/
*.pyc
.venv/
venv/
*.db
*.db-journal
*.db-wal
.env          # ⚠ 绝对不能打包——含 DeepSeek 密钥！
dist/
.vscode/
.idea/
```
