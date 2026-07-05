# AI Panel Studio — 前端

沉浸式 AI 圆桌演播厅前端，基于 React 18 + TypeScript + Vite + Zustand。

---

## 快速启动

### 1. 环境准备

```bash
# Node.js 18+ 推荐
node --version

# 安装依赖
npm install
```

### 2. 配置后端地址

```bash
# 复制环境变量模板（可选，Vite 开发 proxy 已默认转发 /api 到 localhost:8000）
cp .env.example .env
```

开发环境下，Vite 自动将 `/api` 请求代理到 `http://localhost:8000`（见 `vite.config.ts`）。

### 3. 启动开发服务器

```bash
npm run dev
```

默认在 `http://localhost:5173` 启动。

### 4. 生产构建

```bash
npm run build
npm run preview
```

---

## 项目结构

```
frontend/
├── index.html
├── package.json
├── vite.config.ts              # Vite 配置 + API 代理
├── tsconfig.json
├── README.md
│
└── src/
    ├── main.tsx                # 入口
    ├── App.tsx                 # 路由 + ResponsiveShell
    │
    ├── types/
    │   └── index.ts            # TypeScript 类型（对齐后端 api-contract.yaml）
    │
    ├── api/
    │   └── client.ts           # REST 客户端 + SSE EventSource 封装
    │
    ├── store/
    │   └── discussionStore.ts  # Zustand 全局状态（讨论列表）
    │
    ├── styles/
    │   └── index.css           # 全局样式（暗色主题 + 动画 + 响应式）
    │
    ├── components/
    │   ├── base/               # 基础通用组件（7 个，零业务语义）
    │   │   ├── ScrollPanel.tsx
    │   │   ├── ColorBadge.tsx
    │   │   ├── StatusIndicator.tsx
    │   │   ├── Modal.tsx
    │   │   ├── SseStatusBar.tsx
    │   │   ├── HighlightText.tsx
    │   │   └── ResponsiveShell.tsx
    │   │
    │   └── business/           # 业务 UI 组件（10 个）
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
    └── pages/                  # 页面层
        ├── HomePage.tsx        # 首页（卡片列表 + 新建弹窗）
        └── StudioPage.tsx      # 演播厅（useReducer + SSE）
```

---

## 架构关键设计

### 组件三层分层
- **base/** 无业务语义，可跨项目复用
- **business/** 只拼 base 组件 + 调用 `api/client.ts`
- **pages/** 持有状态 + 拼 business 组件

### 会话隔离
- `StudioPage` 使用 `useReducer` 管理单场讨论的全部状态
- 状态随组件挂载创建、随路由离开销毁——不同讨论之间完全隔离
- 切换讨论时 SSE 连接自动断开重连

### SSE 实时推送
- `api/client.ts` → `createSSEConnection()` 封装 EventSource
- 监听 6 种事件：`speech.chunk` / `speech.complete` / `consensus.update` / `divergence.update` / `error` / `heartbeat`
- 断线自动重连（3s），通过 `after_sequence` 参数补偿遗漏数据

### 响应式三档
| 断点 | 布局 | 核心机制 |
|---|---|---|
| ≥1440px | 三栏并排 20/50/30 | flex + 各自 scroll-panel |
| 768-1439px | 上排左+中 / 下排右 | 双层 flex |
| <768px | 三 Tab 单栏 | 顶部 TabBar 切换 |

### 内容隐藏
- 前端**只渲染** `speech.content` / `consensus.content` / `divergence.content` 等自然语言字段
- 所有 SSE event data 中不包含 AI 元数据（已由后端 `_sanitize_content()` 过滤）
- 全局异常提示为通用文案，不泄露原始错误

---

## API 对接

后端服务需先在 `http://localhost:8000` 启动。

Vite 开发代理配置（`vite.config.ts`）：
```typescript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
}
```

生产部署时，可将前端构建产物放在后端 `/static` 目录，或使用 Nginx 反向代理。
