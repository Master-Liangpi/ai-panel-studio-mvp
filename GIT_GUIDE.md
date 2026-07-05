# AI Panel Studio — Git 提交规范

---

## 分支策略

```
main                    ← 可发布主线（受保护）
  ├── develop           ← 开发集成分支
  │   ├── feat/xxx      ← 功能分支
  │   ├── fix/xxx       ← 修复分支
  │   └── refactor/xxx  ← 重构分支
  └── release/x.x.x     ← 发布分支
```

---

## Commit Message 格式

```
<type>(<scope>): <subject>

<body>（可选）

<footer>（可选）
```

### Type 类型

| type | 说明 | 示例 |
|---|---|---|
| `feat` | 新功能 | `feat(backend): 实现嘉宾 AI 自动生成接口` |
| `fix` | Bug 修复 | `fix(sse): 修复断线重连后 sequence_num 跳号` |
| `docs` | 文档变更 | `docs: 更新 E2E 验收方案` |
| `style` | 样式/格式化（不影响逻辑） | `style(frontend): 统一演播厅暗色主题色值` |
| `refactor` | 重构（不增功能不修 bug） | `refactor(llm): 抽取 prompt 模板为常量` |
| `test` | 测试用例 | `test: 追加发言并发场景单元测试` |
| `chore` | 构建/工具/配置 | `chore: 添加 .env.example 到 .gitignore` |
| `perf` | 性能优化 | `perf(db): 为 speeches 表追加联合索引` |

### Scope 范围

| scope | 涉及模块 |
|---|---|
| `backend` | 后端通用（main.py / config / database） |
| `api` | 路由层 |
| `llm` | DeepSeek 调用层（services/llm.py） |
| `sse` | SSE 推送相关 |
| `db` | 数据库相关 |
| `frontend` | 前端通用 |
| `ui` | UI 组件 |
| `pages` | 页面组件 |
| `store` | 状态管理 |
| `docs` | 文档 |

### Subject 规则

- 中文或英文，全文统一（本项目推荐中文）
- 50 字以内
- 不加句号
- 动词开头（实现 / 修复 / 更新 / 追加 / 移除）

---

## 提交示例

```bash
# 功能开发
git commit -m "feat(llm): 实现发言者决策模拟举手/反驳/补充逻辑"

# Bug 修复
git commit -m "fix(sse): 修复客户端断开后队列未清理导致内存泄漏"

# 文档更新
git commit -m "docs: 追加前后端联调校验清单（70+ 检查项）"

# 重构
git commit -m "refactor(api): 将讨论路由参数校验抽取为依赖函数"

# 样式调整
git commit -m "style(frontend): 统一三档断点下 scroll-panel 内边距"

# 多文件跨模块
git commit -m "feat(backend,frontend): 实现多会话数据隔离（5 表 + SSE + store）"
```

---

## 提交粒度

| 层级 | 粒度 | 时机 |
|---|---|---|
| 原子提交 | 1 个逻辑变更 | 每完成一个独立功能点 |
| WIP 提交 | 开发进行中 | `git stash` 或临时分支，不推到远程 |
| 合并提交 | 功能分支合入 develop | `git merge --no-ff feat/xxx` 保留分支轨迹 |

---

## .gitignore 建议

```gitignore
# 环境变量（含密钥）
.env

# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/

# SQLite
*.db
*.db-journal
*.db-wal

# Node
node_modules/
dist/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

> ⚠ `.env` 文件**绝对不能**提交到仓库——它包含 `DEEPSEEK_API_KEY`。
