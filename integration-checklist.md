# AI Panel Studio — 前后端联调校验清单

> 对照 `e2e-acceptance-plan.md` 验收标准，逐项核对前后端对接坑点。
> 每个校验项标注：✅ 已通过 / ⚠ 需排查 / ❌ 未实现。

---

## 一、环境联调前提

| # | 检查项 | 校验方式 | 通过标准 |
|---|---|---|---|
| ENV-01 | 后端 `.env` 已配置 `DEEPSEEK_API_KEY` | `cat backend/.env | grep DEEPSEEK_API_KEY` | 值不是占位符 `sk-your-...`，长度 > 20 |
| ENV-02 | 后端数据库已初始化 | `ls backend/data/ai_panel_studio.db` | 文件存在，`sqlite3` 可打开 5 张表 |
| ENV-03 | 后端启动成功 | `curl http://localhost:8000/api/v1/health` | 返回 `{"status":"ok"}` |
| ENV-04 | 前端启动成功 | 浏览器打开 `http://localhost:5173` | 首页正常渲染，无控制台报错 |
| ENV-05 | Vite proxy 生效 | 浏览器访问 `http://localhost:5173/api/v1/health` | 代理到后端，返回同上 |

---

## 二、API 逐端点联调

### 2.1 讨论会话

| # | 接口 | 校验操作 | 预期结果 | 坑点预警 |
|---|---|---|---|---|
| API-01 | `POST /discussions` | curl 创建讨论 | 201 + 返回 id/title/status=active | title 为空时 400，不是 500 |
| API-02 | `GET /discussions` | 列表查询 | 200 + items[] 按 updated_at 倒序 | panelist_count/speech_count 为聚合子查询，不为 null |
| API-03 | `GET /discussions/{id}` | 详情查询 | 字段完整 | 404 时 error body 含 code="DISCUSSION_NOT_FOUND" |
| API-04 | `PATCH /discussions/{id}` | 改状态为 completed | status 字段更新，updated_at 刷新 | 仅传入变更字段，未传的不重置 |
| API-05 | `DELETE /discussions/{id}` | 级联删除 | 204 + 5 表相关行全部清除 | ⚠ 务必先备份测试数据 |

### 2.2 嘉宾

| # | 接口 | 校验操作 | 预期结果 | 坑点预警 |
|---|---|---|---|---|
| API-06 | `POST .../panelists/generate` | count=5 | 201 + 1 host + 4 experts | ⚠ **DeepSeek 必须可用**；count=0/11 必须 400 |
| API-07 | `GET .../panelists` | 列表查询 | host 字段单独返回，experts[] 不含 host | host 为 null 时前端不崩溃 |
| API-08 | `POST .../panelists` | 手动加 host | 已有 host 时返回 400 BUSINESS_CONFLICT | 错误码区分 VALIDATION_ERROR vs BUSINESS_CONFLICT |
| API-09 | `PATCH .../panelists/{pid}` | 改颜色 | 200 + color 更新 | 不传的字段不覆盖 |
| API-10 | `DELETE .../panelists/{pid}` | 删除嘉宾 | 204 + speeches 表 panelist_id 置 NULL | ⚠ speeches 的 panelist_name 为 LEFT JOIN COALESCE |

### 2.3 发言 + SSE

| # | 接口 | 校验操作 | 预期结果 | 坑点预警 |
|---|---|---|---|---|
| API-11 | `POST .../speeches/next` | 首次触发 | 202 + accepted=true | ⚠ 必须先有嘉宾（host+expert），否则 400 |
| API-12 | SSE `/stream` | 浏览器 EventSource 连接 | text/event-stream + 200 持续 pending | ⚠ CORS 必须允许；Nginx 需 `proxy_buffering off` |
| API-13 | SSE `speech.chunk` | 发言生成中 | 逐 token 推送，delta 为中文文本 | ⚠ 首个 chunk 之前 panelist_id 已确定 |
| API-14 | SSE `speech.complete` | 发言完成 | 完整 Speech JSON，含 panelist_name/color | ⚠ sequence_num 连续递增不跳号 |
| API-15 | SSE `consensus.update` | 共识形成 | 发言完成后 ≤3s 内推送 | ⚠ 首条发言无共识；空发言不推送 |
| API-16 | SSE `divergence.update` | 分歧形成 | 同上 | ⚠ 仅 1 位专家发言时不产生分歧 |
| API-17 | `GET .../speeches` | 历史查询 | sequence_num 升序 | ⚠ after_sequence 正确过滤 |
| API-18 | 并发 `next` | 快速双击按钮 | 第一次 202，第二次 409 | ⚠ 前端防抖 + 后端锁双重保护 |
| API-19 | 并发 `next` 不同讨论 | 两讨论同时触发 | 两个都 202，各自 SSE 独立推送 | ⚠ 后台 asyncio.create_task 不互相阻塞 |

### 2.4 共识/分歧

| # | 接口 | 校验操作 | 预期结果 | 坑点预警 |
|---|---|---|---|---|
| API-20 | `GET .../consensus` | 查共识列表 | updated_at 倒序 | 空列表返回 `{"items":[],"total":0}` 非 null |
| API-21 | `GET .../divergence` | 查分歧列表 | 同上 | sides 字段可能为空字符串，前端兼容 |
| API-22 | SSE 共识合并 | 连续触发含相似观点发言 | total 不增加，已有条目 updated_at 更新 | ⚠ DeepSeek 可能返回重复 topic，后端应去重 |

### 2.5 总结

| # | 接口 | 校验操作 | 预期结果 | 坑点预警 |
|---|---|---|---|---|
| API-23 | `POST .../summary` | 发言 ≥5 条后生成 | 200 + Markdown 内容 + discussion status→completed | ⚠ 无发言时 400 NO_SPEECHES |
| API-24 | `GET .../summary` | 查已生成总结 | 200 或 404 SUMMARY_NOT_FOUND | ⚠ 首次生成后缓存于内存，重启需重新生成 |
| API-25 | 总结后触发 `next` | 在 completed 讨论触发 | 400 DISCUSSION_COMPLETED | 前端按钮置灰 + 后端校验双重保护 |

---

## 三、三大核心校验项重点排查

### 3.1 多会话数据隔离

| # | 排查项 | 操作 | 验证 SQL | 通过标准 |
|---|---|---|---|---|
| ISO-01 | panelists 隔离 | 讨论 A 生成 5 人，讨论 B 生成 3 人 | `SELECT discussion_id, COUNT(*) FROM panelists GROUP BY discussion_id` | 返回两行：42→5, 43→3 |
| ISO-02 | speeches 隔离 | A 触发 10 轮发言，B 无操作 | `SELECT discussion_id, COUNT(*) FROM speeches GROUP BY discussion_id` | 42→10, 43→0 |
| ISO-03 | consensus 隔离 | 同上验证 | `SELECT discussion_id, COUNT(*) FROM consensus_points GROUP BY discussion_id` | 42 有数据，43 无数据 |
| ISO-04 | divergence 隔离 | 同上验证 | 同上 | 同上 |
| ISO-05 | 前端前台切换 | 标签 A `/studio/42`，标签 B `/studio/43`，在 A 中操作 | 标签 B 页面无任何变化 | 嘉宾列表/发言/共识分歧均不变 |
| ISO-06 | 前端 SSE 隔离 | 两个标签各连各自 SSE | Chrome DevTools Network → EventStream | 标签 A 只收到 discussion_id=42 的事件 |
| ISO-07 | 级联删除隔离 | 删除讨论 42 | `SELECT COUNT(*) FROM speeches WHERE discussion_id=42` | → 0；discussion_id=43 的数据完好 |

### 3.2 SSE 实时推送

| # | 排查项 | 操作 | 验证方式 | 坑点 |
|---|---|---|---|---|
| SSE-01 | 连接建立 | 进入演播厅页 | Network 面板 type=text/event-stream | ⚠ 若 type=application/octet-stream，检查 CORS 和 content-type header |
| SSE-02 | 流式 token | 触发发言 | EventStream 子标签逐行显示 data | ⚠ chunk 丢失时 content 不完整，后端需保证原子性 |
| SSE-03 | 发言完成 | `speech.complete` 事件 | data JSON 含 id/content/panelist_name | ⚠ created_at 格式为 ISO 8601，前端 new Date() 兼容 |
| SSE-04 | 心跳 | 15s 不操作 | 出现 `event: heartbeat` `data: {}` | ⚠ 前端忽略 heartbeat，不做任何 UI 变更 |
| SSE-05 | 断线重连 | DevTools Network → Offline → Online | 3s 内自动重连 + after_sequence 补偿 | ⚠ `after_sequence` 取最后 speech.sequence_num，不是 speech.id |
| SSE-06 | 长时间运行 | 保持连接 10 分钟 | 内存不持续增长（Tab 内存 < 200MB） | ⚠ 检查 SSE queue 未清理的死连接 |

### 3.3 LLM 敏感信息隐藏

| # | 排查项 | 检查方式 | 通过标准 | 坑点 |
|---|---|---|---|---|
| SEC-01 | 发言卡片 | 肉眼检查中栏全部 SpeechCard content | 纯中文对话，无 JSON/模型名/prompt | ⚠ 检查 `_sanitize_content()` 是否覆盖所有异常格式 |
| SEC-02 | 共识卡片 | 肉眼检查 ConsensusItem content/topic | 自然语言，无 `"topic"` `"content"` 字段名 | ⚠ LLM 分析结果中的内部字段（speaker_ids）不在前端展示 |
| SEC-03 | 分歧卡片 | 肉眼检查 DivergenceItem | 同上，sides 为自然格式 | 同上 |
| SEC-04 | 总结面板 | 肉眼检查 Markdown 总结 | 报告式行文，无 ` response` 标记 | ⚠ 检查 `generate_summary` prompt 是否要求"直接从 ## 开始" |
| SEC-05 | Network 响应体 | DevTools Network → Response 标签 | JSON value 不含模型元数据 | ⚠ 检查 `reason` 字段不通过 SSE 广播 |
| SEC-06 | Console 日志 | DevTools Console | 生产构建无 DeepSeek 原始响应日志 | ⚠ 开发模式下 `logger.info` 含 `_internal_reason`，生产需关闭 |
| SEC-07 | HTML 源码 | 查看页面源代码 | 搜索 "DeepSeek" "prompt" "system" "sk-" → 0 匹配 | 钥匙绝对不能出现在 HTML 源码里 |
| SEC-08 | 错误提示 | 断网后触发发言 | 提示"服务暂时不可用" | 不暴露 API 端点 URL、HTTP 状态码、异常堆栈 |

---

## 四、数据流时序校验

对照接口契约中定义的 SSE 事件时序：

```
POST /speeches/next (202)
  → [后端异步]
  → decide_next_speaker (LLM 决策，~1s)
  → SSE speech.chunk × N (流式 token)
  → INSERT INTO speeches
  → SSE speech.complete
  → analyze_consensus_divergence (LLM 分析，~2s)
  → SSE consensus.update / divergence.update
```

| # | 检查点 | 预期延迟 | 验证方式 |
|---|---|---|---|
| TIME-01 | POST 到首个 chunk | ≤ 3s | curl + `time` 计时 |
| TIME-02 | speech.complete 到 consensus.update | ≤ 3s | SSE 事件时间戳差值 |
| TIME-03 | 连续触发 5 次 next | 每次间隔 ≥5s（等待上一条完成） | 手动操作 + 观察 generatingSpeech 状态 |
| TIME-04 | sequence_num | 连续递增 1→N，无跳号 | `SELECT sequence_num FROM speeches WHERE discussion_id=? ORDER BY id` |

---

## 五、常见对接坑点汇总

| # | 症状 | 可能原因 | 排查方向 |
|---|---|---|---|
| PIT-01 | 前端 SSE 连接立即断开 | CORS 未配置 `text/event-stream` | 检查后端 `main.py` CORS middleware + Nginx `proxy_buffering off` |
| PIT-02 | 发言卡片姓名显示 "(已离场嘉宾)" | panelist 被删除后 speeches LEFT JOIN 返回 NULL | 正常行为，COALESCE 兜底 |
| PIT-03 | 共识/分歧条目不更新 | DeepSeek 分析超时或返回空 | 检查后端日志 `共识/分歧分析调用失败` |
| PIT-04 | 新建讨论后前端卡片列表未刷新 | Zustand store 未触发 fetchList | 检查 `createDiscussion` 方法中 `await get().fetchList()` |
| PIT-05 | 切换讨论后仍看到旧数据 | StudioPage 的 useReducer 状态残留 | 检查 `key` 或 `useEffect` 清理逻辑 |
| PIT-06 | 手机端三栏布局只显示第一栏 | CSS 媒体查询断点不生效 | 检查 `<meta viewport>` 标签 + ResponsiveShell 逻辑 |
| PIT-07 | 总结生成后 discussion.status 未变 | 后端 summary 服务未 UPDATE | 检查 `generate_summary_for_discussion` 中 UPDATE 语句 |
| PIT-08 | 断线重连后遗漏发言 | after_sequence 参数未传递 | 检查 `createSSEConnection` 中 `lastSequence` 更新时机 |
| PIT-09 | 流式发言光标跳动 | speech.chunk 触发频繁重渲染 | 检查 React.memo/useMemo 优化 SpeechCard |
| PIT-10 | keynote: 后端 .env 未加载 | `python-dotenv` 未安装或路径不对 | `pip install python-dotenv` + 确认 .env 在 backend/ 根目录 |

---

## 六、联调完成签核

| 序号 | 阶段 | 签核条件 |
|---|---|---|
| S1 | 环境就绪 | ENV-01 ~ ENV-05 全部 ✅ |
| S2 | API 端点 | API-01 ~ API-25 全部 ✅ |
| S3 | 数据隔离 | ISO-01 ~ ISO-07 全部 ✅ |
| S4 | SSE 推送 | SSE-01 ~ SSE-06 全部 ✅ |
| S5 | 内容隐藏 | SEC-01 ~ SEC-08 全部 ✅ |
| S6 | 时序延迟 | TIME-01 ~ TIME-04 全部 ✅ |
