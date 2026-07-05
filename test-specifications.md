# AI Panel Studio — 测试规范（TDD 先行）

> 本阶段只产出测试规格，不写业务实现代码、不写大模型调用逻辑。
> 每个模块分三层用例：正常 / 边界 / 异常，均以表格 + 伪代码形式呈现。

---

## 模块一：嘉宾自动生成

### 1.1 正常用例

| 编号 | 场景 | 输入 | 期望结果 | 校验点 |
|---|---|---|---|---|
| N1.1 | 标准 5 人阵容 | `topic="AI 监管应由政府主导还是行业自律"`, `count=5` | 返回 5 人（1 host + 4 expert），每人有 name/title/stance/color | `items.length === 5`；`host.role === 'host'`；全部 expert.role === 'expert' |
| N1.2 | 最少人数（仅主持人） | `count=1` | 返回 1 人，role=host | 不报错；`host` 不为 null |
| N1.3 | 最多人数 | `count=10` | 返回 10 人（1 host + 9 expert） | `items.length === 10` |
| N1.4 | 立场互斥 | 同 N1.1 | 任意两人 `stance` 不重复（编辑距离 ≥ 阈值） | 两两比对 stance 字符串相似度 < 0.7 |
| N1.5 | 职业互斥 | 同 N1.1 | 任意两人 `title` 不重复 | 两两比对 title，不含完全相同的子串 |
| N1.6 | 颜色互斥 | 同 N1.1 | 任意两人 `color` 不重复 | `new Set(colors).size === count`；全部为合法 Hex |
| N1.7 | 颜色合法性 | 同 N1.1 | 所有 color 为有效 Hex | 每个匹配 `/^#[0-9A-Fa-f]{6}$/` |
| N1.8 | 立场覆盖话题相关维度 | `topic="AI 监管"`, `count=5` | 5 人立场应覆盖话题的正、反、中立至少各一 | 扫描 stance 文本，存在"主张/支持/应"、也存在"反对/不应/质疑" |

### 1.2 边界用例

| 编号 | 场景 | 输入 | 期望结果 | 校验点 |
|---|---|---|---|---|
| B1.1 | count 恰好为 1 | `count=1` | 正常生成 1 人（主持人） | 不报错，host 有效 |
| B1.2 | count 恰好为 10 | `count=10` | 正常生成 10 人 | 不报错，10 人全部唯一 |
| B1.3 | 话题极短（2 字） | `topic="AI"`, `count=3` | 正常生成 3 人 | 不因话题过短而崩溃；立场仍有区分度 |
| B1.4 | 话题极长（2000 字） | `topic=<2000 字符>` | 正常生成 | 不截断、不超时 |
| B1.5 | topic_override 覆盖原 topic | `topic="旧话题"`, 请求体 `topic_override="新话题"` | 以 topic_override 为准生成 | 嘉宾立场反映的是"新话题"而非"旧话题" |
| B1.6 | 两次调用生成不重复 | 同一 topic 调用两次 `count=5` | 两次结果不同 | 姓名、立场不完全相同（AI 非确定性输出） |

### 1.3 异常用例

| 编号 | 场景 | 输入 | 期望结果 | 校验点 |
|---|---|---|---|---|
| E1.1 | 人数为 0 | `count=0` | 返回 400 `VALIDATION_ERROR` | `code === 'VALIDATION_ERROR'`；message 含"人数" |
| E1.2 | 人数超上限 | `count=11` | 返回 400 | `code === 'VALIDATION_ERROR'`；message 含"1~10" |
| E1.3 | 人数为负数 | `count=-1` | 返回 400 | 同上 |
| E1.4 | 讨论 ID 不存在 | `discussion_id=99999` | 返回 404 `DISCUSSION_NOT_FOUND` | `code === 'DISCUSSION_NOT_FOUND'` |
| E1.5 | DeepSeek 不可用 | 模拟网络超时 | 返回 502 `AI_SERVICE_UNAVAILABLE` | 不返回空列表、不静默失败 |
| E1.6 | DeepSeek 返回格式非法 | 模拟返回缺少 stance 字段的 JSON | 返回 500 或重试后 502 | 前端收到的要么是完整合法数据，要么是明确错误 |
| E1.7 | 生成结果出现重复立场 | 对返回结果做后置校验 | 若检测到重复立场的相似度 ≥ 0.7，自动重新生成一次 | 最终返回结果通过立唯一性检查 |
| E1.8 | 生成结果出现重复颜色 | 对返回结果做后置校验 | 若颜色重复，自动重新分配颜色 | 最终返回结果颜色唯一 |

### 1.4 测试流程伪代码

```
describe("嘉宾自动生成")
  before_all:
    seed_discussion(title="测试讨论")  → discussion_id

  // ---- 正常 ----
  test("N1.1 标准 5 人阵容")
    res = POST /discussions/{discussion_id}/panelists/generate { count: 5 }
    assert res.status == 201
    body = res.json()
    assert body.host.role == "host"
    assert body.experts.length == 4
    assert body.items.length == 5

    // 唯一性校验
    stances  = body.items.map(p => p.stance)
    colors   = body.items.map(p => p.color)
    titles   = body.items.map(p => p.title)
    assert all_unique_within_similarity(stances, threshold=0.7)
    assert new Set(colors).size == 5
    assert all_unique(titles)

    // 颜色格式校验
    for c in colors: assert c matches /^#[0-9A-Fa-f]{6}$/

    // 立场覆盖校验
    has_pro  = stances.any(s => s contains "主张" or "支持" or "应")
    has_con  = stances.any(s => s contains "反对" or "不应" or "质疑")
    assert has_pro and has_con

  test("N1.4~N1.7 独立用例同样结构，只是断言侧重不同")

  // ---- 边界 ----
  test("B1.1 count=1")
    res = POST .../generate { count: 1 }
    assert res.status == 201
    assert res.json().host.role == "host"
    assert res.json().experts.length == 0

  test("B1.2 count=10")
    res = POST .../generate { count: 10 }
    assert res.status == 201
    assert res.json().items.length == 10
    assert all_unique_colors_and_stances(res.json())

  test("B1.3 topic 极短")
    res = POST .../generate { count: 3, topic_override: "AI" }
    assert res.status == 201  // 不崩溃
    assert res.json().items.length == 3

  test("B1.5 topic_override 生效")
    res = POST .../generate { count: 3, topic_override: "量子计算" }
    assert res.status == 201
    // 验证立场含"量子"相关词汇
    stances = res.json().items.map(p => p.stance).join(" ")
    assert stances contains "量子" or "计算" or "qubit"

  // ---- 异常 ----
  test("E1.1 count=0")
    res = POST .../generate { count: 0 }
    assert res.status == 400
    assert res.json().code == "VALIDATION_ERROR"

  test("E1.2 count=11")
    res = POST .../generate { count: 11 }
    assert res.status == 400

  test("E1.4 discussion 不存在")
    res = POST /discussions/99999/panelists/generate { count: 3 }
    assert res.status == 404
    assert res.json().code == "DISCUSSION_NOT_FOUND"

  test("E1.5 AI 不可用")
    mock_deepseek_timeout()
    res = POST .../generate { count: 3 }
    assert res.status == 502
    assert res.json().code == "AI_SERVICE_UNAVAILABLE"

  test("E1.7 重复立场自动重试")
    // 注入 mock：第一次返回含重复立场，第二次正常
    mock_deepseek_response_sequence([
      { stances: ["支持监管","支持监管","中立","反对","反对"] },  // 重复
      { stances: ["支持监管","反对监管","中立观望","有条件支持","完全放任"] }  // 唯一
    ])
    res = POST .../generate { count: 5 }
    assert res.status == 201
    assert all_unique_within_similarity(res.json().items.map(p => p.stance))
```

---

## 模块二：AI 自主发言逻辑

### 2.1 正常用例

| 编号 | 场景 | 输入 | 期望结果 | 校验点 |
|---|---|---|---|---|
| N2.1 | 主持人开场 | 讨论刚建好，已生成 5 位嘉宾，首次调用 `POST /speeches/next` | SSE 推送 `speech.complete`，`panelist_id` 为主持人 | `panelist_id === host.id`；content 包含欢迎/介绍/引出议题；`sequence_num === 1` |
| N2.2 | 专家轮流发言（非固定顺序） | 调用 N 次 `next` | 相邻两次发言的 panelist_id **不同**（不会同一个人连续说两次，除非举手指定为唯一发言人） | `speeches[i].panelist_id !== speeches[i-1].panelist_id`（多数情况） |
| N2.3 | 发言长度控制 | 任意一次 `next` | 每段发言 1-2 句话，即 20~200 字 | `sentence_count in [1,2]`；`char_count between 20 and 200` |
| N2.4 | 反驳场景 | 某位专家观点与上一位明确冲突时 | 下一位发言应出现反驳逻辑（content 含"但是""然而""不认同""我不同意"等转折词） | content 匹配反驳关键词；被反驳方的 stance 与反驳方 content 矛盾 |
| N2.5 | 补充场景 | 某位专家的立场与上一位相近 | 下一位发言应出现补充/强化（content 含"我同意""补充一点""进一步说""确实"等） | content 匹配补充关键词；两方 stance 相似但 content 有新信息 |
| N2.6 | 主持人串场 | 连续多轮专家发言后 | 主持人介入串场："刚才几位嘉宾的观点很有启发…下面请 X 谈谈…" | panelist_id 为 host；content 含总结前文 + 引出下一位 |
| N2.7 | 主持人收尾 | 调用 `POST /summary` 或达到预定轮次 | 主持人做总结发言："今天的讨论非常精彩…核心共识是…分歧在于…" | 收尾发言 sequence_num 最大；content 提到共识和分歧 |
| N2.8 | 随机性校验 | 同一讨论从相同状态触发 10 次 `next` | 10 次选出的下一位嘉宾**不是**完全相同的 | `new Set(selected_panelist_ids).size > 3`（多样性） |
| N2.9 | 举手抢答 | 模拟 AI 内部决策 | 某次触发后，`speech.chunk` 延迟比其他轮次明显更短（抢答快） | 记录每次 `next` 请求到 `speech.chunk` 首 token 延迟，存在差异性 |

### 2.2 边界用例

| 编号 | 场景 | 输入 | 期望结果 | 校验点 |
|---|---|---|---|---|
| B2.1 | 最少嘉宾（1 host + 1 expert） | 只有 2 位嘉宾，连续触发 `next` | host 开场 → expert 发言 → host 串场 → expert 发言（交替合理） | 不出现同一人连续 3 次以上发言 |
| B2.2 | 最多嘉宾（1 host + 9 expert） | 10 位嘉宾 | 每位专家至少被选中一次（在足够轮次下） | 触发 20 次 `next` 后，覆盖全部 9 位 expert |
| B2.3 | 带 prompt_hint 的引导 | `prompt_hint="请嘉宾针对数据隐私发表看法"` | 下一位发言 content 应涉及"数据隐私" | content 含"隐私""数据保护""个人信息"等关键词 |
| B2.4 | 主持人开场后再开场 | 已在 sequence_num≥1 的状态再触发且指定主持人 | 不应再产出第二段开场白 | 第二段不是"欢迎各位嘉宾"式的开场模板 |
| B2.5 | 极短讨论 | 开场后立即调用 summary | 主持人收尾 + 总结，不因发言太少而崩溃 | sequence_num 可能只有 2-3 条，但流程正常结束 |
| B2.6 | 超长讨论（100 轮） | 连续触发 `next` 100 次 | 所有发言正常落库 + SSE 推送 | 不出现内存溢出、序号跳变、内容质量明显下降 |

### 2.3 异常用例

| 编号 | 场景 | 输入 | 期望结果 | 校验点 |
|---|---|---|---|---|
| E2.1 | 无嘉宾时触发发言 | 讨论无 panelist | 返回 400 `NO_PANELISTS` | 不调用 DeepSeek（节省 token） |
| E2.2 | 只有主持人无专家 | 只有 1 位 host | 返回 400 `NO_EXPERTS` | message 含"至少需要" |
| E2.3 | 讨论已结束 | `status=completed` | 返回 400 `DISCUSSION_COMPLETED` | 不生成新发言 |
| E2.4 | 讨论已暂停 | `status=paused` | 返回 400 或静默拒绝 | 不生成新发言、不推送 SSE |
| E2.5 | 并发触发（同一讨论） | 连续快速 POST 两次 `next` | 第一次返回 202，第二次返回 409 `SPEECH_IN_PROGRESS` | 不产生两个并发生成的发言 |
| E2.6 | DeepSeek 中途超时 | 模拟流式生成到一半超时 | SSE 推送 `event: error`，`generatingSpeech` 重置为 false | 讨论状态回退到可重试；已输出的 chunk 不入库 |
| E2.7 | DeepSeek 返回空内容 | 模拟返回 content="" | 不推送 `speech.complete`；推送 `event: error` | 空发言不入库，`sequence_num` 不递增 |
| E2.8 | DeepSeek 返回内容过长 | 模拟返回 500 字以上 | 后处理截断至 2 句内，或推送 `event: error` | 要么合规长度落库，要么拒绝 |
| E2.9 | 讨论 ID 不存在 | `discussion_id=99999` | 返回 404 | 同模块一 |

### 2.4 测试流程伪代码

```
describe("AI 自主发言逻辑")
  before_each:
    discussion_id = seed_discussion()
    seed_panelists(discussion_id, count=5)  // 1 host + 4 experts
    connect_sse(discussion_id)  // 建立 SSE 监听，收集所有推送事件

  // ---- 正常 ----
  test("N2.1 主持人开场")
    events = []
    sse.on("speech.complete", e => events.push(e))

    res = POST /discussions/{discussion_id}/speeches/next
    assert res.status == 202
    await_until(() => events.length >= 1, timeout=15_000)

    speech = events[0]
    assert speech.sequence_num == 1
    assert speech.panelist_id == host.id
    assert speech.content contains any_of ["欢迎","今天","讨论","议题","各位"]

  test("N2.2 非固定轮流发言")
    speeches = []
    sse.on("speech.complete", s => speeches.push(s))

    for i in 1..10:
      POST /discussions/{discussion_id}/speeches/next
      await_speech_complete(timeout=15_000)

    // 校验：不存在同一人连续 3 次以上的情况
    for i in 2..speeches.length-1:
      triplet = speeches.slice(i-2, i+1).map(s => s.panelist_id)
      assert !(triplet[0]==triplet[1] && triplet[1]==triplet[2]),
             "同一嘉宾连续发言不得超过 2 次"

  test("N2.3 发言长度")
    for speech in speeches:
      sentences = split_sentences(speech.content)
      assert sentences.length in [1, 2], "必须为 1~2 句话"
      assert speech.content.length between 20 and 200

  test("N2.4 反驳逻辑")
    // 找到一对 stance 冲突的嘉宾
    pro  = panelists.find(p => p.stance contains "支持")
    con  = panelists.find(p => p.stance contains "反对")

    // 在 pro 发言后触发，观察是否有反驳
    trigger_until_panelist_speaks(con.id)
    last = speeches.last()
    assert last.panelist_id == con.id
    assert last.content contains any_of ["但是","然而","不同意","不认同","反对"]

  test("N2.5 补充逻辑")
    // 找到一对立场相近的嘉宾，验证后一位的发言含补充关键词
    similar_pair = find_two_similar_stance_panelists()
    trigger_until_panelist_speaks(similar_pair[1].id)
    last = speeches.last()
    assert last.content contains any_of ["同意","补充","进一步","确实","没错"]

  test("N2.6 主持人串场")
    // 观察：expert 连续发言 ≥4 次后，下一次应为 host
    expert_streak = 0
    for speech in speeches:
      if speech.panelist_id != host.id:
        expert_streak++
      else:
        expert_streak = 0
      assert expert_streak <= 4, "专家连续发言超 4 次，主持人未串场"

  test("N2.7 主持人收尾")
    POST /discussions/{discussion_id}/summary
    // 此时应生成一段收尾发言
    await_speech_complete()
    final_speech = speeches.last()
    assert final_speech.panelist_id == host.id
    assert final_speech.content contains any_of ["总结","共识","分歧","精彩","感谢"]

  test("N2.8 随机性")
    // 同一状态触发 10 次，检查下一位发言人不总是同一个
    panelist_picks = []
    for i in 1..10:
      // 使用独立副本状态
      state = clone_discussion_state(discussion_id)
      next_id = ai_decide_next_speaker(state)
      panelist_picks.push(next_id)
    assert new Set(panelist_picks).size > 1, "应有多样性"

  // ---- 边界 ----
  test("B2.1 2 人讨论")
    small_disc = setup_discussion_with_panelists(1_host + 1_expert)
    speeches = trigger_n_speeches(small_disc, 8)
    // 不应出现同一人连续 3 次以上
    assert no_three_consecutive_same_speaker(speeches)

  test("B2.2 10 人全覆盖")
    big_disc = setup_discussion_with_panelists(1_host + 9_experts)
    speeches = trigger_n_speeches(big_disc, 20)
    speaker_ids = new Set(speeches.map(s => s.panelist_id))
    all_expert_ids = big_disc.panelists.filter(p => p.role=="expert").map(p => p.id)
    assert all_expert_ids.every(id => speaker_ids.has(id)),
           "所有专家至少发言一次"

  test("B2.3 prompt_hint 引导")
    res = POST .../speeches/next { prompt_hint: "请讨论数据隐私问题" }
    assert res.status == 202
    speech = await_speech_complete()
    assert speech.content contains any_of ["隐私","数据保护","个人信息","GDPR"]

  test("B2.6 100 轮压力")
    for i in 1..100:
      POST .../speeches/next
      await_speech_complete(timeout=20_000)
    assert speeches.length == 100 + 1  // +1 开场
    assert speeches.last().sequence_num == speeches.last().id 对应的序号
    // 无内存泄漏：进程内存 < 500MB

  // ---- 异常 ----
  test("E2.1 无嘉宾")
    empty_disc = seed_discussion()  // 无 panelist
    res = POST /discussions/{empty_disc}/speeches/next
    assert res.status == 400
    assert res.json().code == "NO_PANELISTS"

  test("E2.3 已结束")
    completed_disc = setup_and_complete_discussion()
    res = POST /discussions/{completed_disc}/speeches/next
    assert res.status == 400
    assert res.json().code == "DISCUSSION_COMPLETED"

  test("E2.5 并发冲突")
    p1 = POST /discussions/{id}/speeches/next   // 立即发送
    p2 = POST /discussions/{id}/speeches/next   // p1 未完成时发送
    r1 = await p1
    r2 = await p2
    assert r1.status == 202
    assert r2.status == 409
    assert r2.json().code == "SPEECH_IN_PROGRESS"

  test("E2.6 超时处理")
    mock_deepseek_streaming_timeout(after_tokens=5)
    res = POST .../speeches/next
    assert res.status == 202
    sse_events = await_collect_sse_until("error", timeout=35_000)
    assert sse_events.last().code == "AI_GENERATION_FAILED"
    // 确认 speech 表无新增
    speech_count_after = GET .../speeches → total
    assert speech_count_after == speech_count_before
```

---

## 模块三：共识分歧提取

### 3.1 正常用例

| 编号 | 场景 | 输入 | 期望结果 | 校验点 |
|---|---|---|---|---|
| N3.1 | 首次共识形成 | 两位专家连续发言，内容有明确交集（都提到"安全是底线"） | `consensus.update` SSE 事件推送，新增 1 条共识 | `topic` 含"安全"；`content` 含双方观点；`latest_speech_id` 为最新发言 ID |
| N3.2 | 共识强化 | 第三位专家发言也呼应同一共识主题 | 已有共识条目被**更新**（非新增）：`content` 追加第三人观点，`updated_at` 变化 | `id` 不变；`content` 变长或涵盖更多嘉宾；`latest_speech_id` 更新 |
| N3.3 | 首次分歧形成 | 两位专家发言立场冲突（如"立法必要" vs "立法会扼杀创新"） | `divergence.update` SSE 事件推送，新增 1 条分歧 | `sides` 字段明确区分两方；`topic` 概括分歧核心 |
| N3.4 | 分歧深化 | 第四位专家发言加入分歧的某一方 | 对应分歧条目 `updated_at` 更新，`sides` 更新各方人数/名单 | `id` 不变；`sides` 字段人数增加 |
| N3.5 | 分歧消解（转为共识） | 分歧一方立场调整，发言表示"重新考虑后同意对方" | 分歧条目被**删除**（或标记为已解决）；可能新增共识 | divergence 列表 `total` 减 1；或新增/更新 consensus |
| N3.6 | 多条共识并存 | 讨论涉及多个子话题，各自形成独立共识 | 同一讨论下多条共识，`topic` 互不相同 | `consensus.items` 按 `topic` 分组不重复 |
| N3.7 | 多条分歧并存 | 讨论有多个维度分歧 | 同一讨论下多条分歧，`topic` 互不相同 | `divergence.items` 按 `topic` 分组不重复 |
| N3.8 | 重复观点自动合并 | 第 N 位嘉宾说了与前人几乎相同的话 | 不产生新共识/分歧条目，而是更新已有条目（合并） | 共识/分歧 total 不因重复观点而增加 |
| N3.9 | 每句发言后同步更新 | 每次 `speech.complete` 后 | 1~2 秒内必有 `consensus.update` 或 `divergence.update`（或两者都有） | SSE 事件时序：`speech.complete` → （短暂计算） → `consensus.update`/`divergence.update` |
| N3.10 | 新更新的条目高亮标记 | 同 N3.9 | 响应体中 `highlight=true`（或 SSE 事件带标记） | 前端可据此决定高亮动画 |

### 3.2 边界用例

| 编号 | 场景 | 输入 | 期望结果 | 校验点 |
|---|---|---|---|---|
| B3.1 | 第一句发言（无比较基准） | 主持人开场白后 | 不产生任何共识/分歧 | `consensus.items.length === 0`；`divergence.items.length === 0` |
| B3.2 | 仅一位专家发言 | 主持人开场 + 仅 1 位专家发言 | 无共识/分歧（无其他专家可比较） | 同上 |
| B3.3 | 空发言内容 | `content=""` 的发言 | 跳过分析，不触发共识/分歧更新 | 不调用 DeepSeek 分析接口；不推送任何 update 事件 |
| B3.4 | 极短发言（单字） | `content="嗯"` 或 `content="对"` | 可能不产生新共识/分歧，或仅更新现有条目的置信度 | 不因极短内容而崩溃；不产生无意义的 topic |
| B3.5 | 极长发言（2000 字） | 一段包含多个子论点的长发言 | 可能同时触发多条共识和/或分歧的更新 | 分析覆盖所有子论点，不遗漏、不截断 |
| B3.6 | 全部达成共识（无分歧） | 经过多轮后所有专家立场趋同 | 分歧列表可能缩减为 0；共识列表涵盖全部议题 | `divergence.items.length === 0`；`consensus.items.length >= 1` |
| B3.7 | 全部分歧无共识 | 所有专家各说各话，无任何共同点 | 共识为空（或仅有主持人总结的"大家同意继续讨论"），分歧多条 | `consensus.items` 可能为 0；不强制编造不存在的共识 |
| B3.8 | 频繁连续更新同一共识 | 连续 5 句发言都触碰同一共识主题 | 1 条共识被更新 5 次，而非生成 5 条 | `consensus.items` 中该 topic 只有 1 条记录，`updated_at` 逐次更新 |

### 3.3 异常用例

| 编号 | 场景 | 输入 | 期望结果 | 校验点 |
|---|---|---|---|---|
| E3.1 | 发言不属于任何讨论 | `speech.discussion_id = NULL` | 分析跳过，不更新任何讨论的共识/分歧 | 不写脏数据到其他讨论 |
| E3.2 | 发言所属讨论不存在 | `discussion_id=99999` | 404 或静默跳过 | 不产生孤儿共识/分歧记录 |
| E3.3 | DeepSeek 分析超时 | 分析接口 30s 未响应 | 该次分析放弃，已落库的发言不受影响；SSE 推送 `event: error` 告知"共识/分歧分析未完成" | 发言数据完整；现有共识/分歧不变；不阻塞后续发言 |
| E3.4 | DeepSeek 返回非法结构 | 分析结果 JSON 缺少 topic 字段 | 记录日志告警，丢弃本次分析结果 | 不写入不完整的共识/分歧行；前端无感知 |
| E3.5 | 辩论内容极端/敏感 | 讨论中出现政治敏感词 | 分析正常进行，不应因内容敏感而崩溃 | 共识/分歧 topic/content 聚焦议题本身，不放大敏感内容 |
| E3.6 | 并发分析冲突 | 两条发言几乎同时落库，触发两次分析 | 串行处理，或乐观锁保证同一条共识不被并发覆写 | 最终数据一致；`updated_at` 反映最后一次更新 |

### 3.4 测试流程伪代码

```
describe("共识分歧提取")
  before_each:
    discussion_id = seed_discussion_with_panelists(5)
    connect_sse(discussion_id)

  // ---- 正常 ----
  test("N3.1 首次共识形成")
    // 构造两句观点相似的发言
    s1 = inject_speech(discussion_id, panelist_A, "AI 安全是必须守住的底线，这点没有商量余地")
    s2 = inject_speech(discussion_id, panelist_B, "我完全同意，安全问题是第一优先级的")
    trigger_consensus_analysis(discussion_id, latest_speech_id=s2.id)

    consensus = await_sse_event("consensus.update")
    assert consensus.topic contains "安全"
    assert consensus.content contains panelist_A.name
    assert consensus.content contains panelist_B.name
    assert consensus.latest_speech_id == s2.id

  test("N3.2 共识强化")
    s3 = inject_speech(discussion_id, panelist_C, "安全是前提，但我想补充：安全标准要统一")
    trigger_consensus_analysis(discussion_id, latest_speech_id=s3.id)

    event = await_sse_event("consensus.update")
    same_consensus = GET /discussions/{id}/consensus
                     → items.find(c => c.id == event.id)
    assert same_consensus.content contains panelist_C.name     // 第三人被纳入
    assert same_consensus.updated_at > same_consensus.created_at

  test("N3.3 首次分歧形成")
    s4 = inject_speech(discussion_id, panelist_D, "我认为立法监管会严重拖慢创新节奏，行业自律才是出路")
    trigger_divergence_analysis(discussion_id, latest_speech_id=s4.id)

    divergence = await_sse_event("divergence.update")
    assert divergence.sides contains "立法" or "自律"
    assert divergence.topic != ""                // 有实质性 topic
    assert divergence.content.length > 20        // 有实质性内容

  test("N3.8 重复观点合并")
    before_count = GET .../consensus → total
    // 注入与之前几乎相同的观点
    inject_speech(discussion_id, panelist_E,
      "安全底线确实不能动摇，我跟前面几位意见一致")
    trigger_consensus_analysis(discussion_id, latest_speech_id=latest.id)

    after_count = GET .../consensus → total
    assert after_count == before_count  // 不新增，更新已有

  test("N3.9 每句发言同步更新时序")
    sse_timeline = []
    sse.on("*", e => sse_timeline.push({ event: e.type, time: now(), data: e }))

    POST .../speeches/next
    await sleep(5_000)

    // 提取时序
    speech_complete_time = sse_timeline.find(e => e.event=="speech.complete").time
    consensus_time       = sse_timeline.find(e => e.event=="consensus.update")?.time
    divergence_time      = sse_timeline.find(e => e.event=="divergence.update")?.time

    if consensus_time:
      assert consensus_time - speech_complete_time < 3000  // 3 秒内
    if divergence_time:
      assert divergence_time - speech_complete_time < 3000

  test("N3.5 分歧消解")
    // 模拟：分歧一方改变立场
    inject_speech(discussion_id, panelist_D,
      "重新考虑之后，我认可立法兜底的必要性，之前的立场过于绝对了")
    trigger_analysis(discussion_id, latest_speech_id=latest.id)

    // 检查原分歧是否被移除或标记已解决
    divergences = GET .../divergence
    assert divergences.items.every(d => d.topic != "监管手段：立法 vs 自律")
           or divergences.items.find(d => d.topic=="监管手段...").status=="resolved"

  // ---- 边界 ----
  test("B3.1 第一句发言无共识")
    fresh_disc = setup_fresh_discussion()
    first_speech = inject_speech(fresh_disc, host, "欢迎各位嘉宾，今天讨论AI监管问题")
    trigger_analysis(fresh_disc, latest_speech_id=first_speech.id)

    await sleep(2_000)
    consensus  = GET /discussions/{fresh_disc}/consensus
    divergence = GET /discussions/{fresh_disc}/divergence
    assert consensus.total == 0
    assert divergence.total == 0

  test("B3.3 空发言不触发分析")
    empty_speech = inject_speech(discussion_id, panelist_A, "")
    analysis_called = spy_on_deepseek_analysis_call()
    assert analysis_called == false
    // 无 SSE 事件推送
    sse_events = collect_sse_for(3_000)
    assert sse_events.none(e => e.type in ["consensus.update","divergence.update"])

  test("B3.8 同 topic 只更新不重复")
    // 连续 5 句都提到"安全"
    for i in 1..5:
      inject_speech(discussion_id, random_panelist(), f"关于安全，我的第{i}点看法是...")
      trigger_analysis(discussion_id, latest_speech_id=latest.id)

    consensus = GET .../consensus
    safety_items = consensus.items.filter(c => c.topic contains "安全")
    assert safety_items.length == 1  // 合并为 1 条
    assert safety_items[0].updated_at > safety_items[0].created_at  // 确实更新过

  // ---- 异常 ----
  test("E3.2 孤儿发言")
    orphan_speech = { discussion_id: 99999, panelist_id: 1, content: "..." }
    // 直接调用内部分析函数
    result = call_analysis_internal(orphan_speech)
    assert result == "SKIPPED" or result.error_code == "DISCUSSION_NOT_FOUND"

  test("E3.3 分析超时不阻塞")
    mock_deepseek_analysis_timeout(35_000)
    s5 = inject_speech(discussion_id, panelist_A, "正常发言内容...")
    trigger_analysis_with_timeout(discussion_id, latest_speech_id=s5.id, timeout=30_000)

    sse_event = await_sse_event("error", timeout=35_000)
    assert sse_event.code == "AI_GENERATION_FAILED" or "ANALYSIS_TIMEOUT"

    // 验证：现有共识/分歧未被污染
    consensus_after  = GET .../consensus
    divergence_after = GET .../divergence
    assert consensus_after == consensus_before
    assert divergence_after == divergence_before

    // 验证：后续发言可以正常触发分析
    s6 = inject_speech(discussion_id, panelist_B, "我认为...")
    trigger_analysis(discussion_id, latest_speech_id=s6.id)
    event = await_sse_event("consensus.update", timeout=15_000)
    assert event != null  // 后续正常

  test("E3.6 并发分析数据一致性")
    // 模拟两句话几乎同时落库
    s_a = inject_speech(discussion_id, panelist_A, "观点 A...")
    s_b = inject_speech(discussion_id, panelist_B, "观点 B...")

    // 并发触发两次分析
    await Promise.all([
      trigger_analysis_async(discussion_id, s_a.id),
      trigger_analysis_async(discussion_id, s_b.id),
    ])

    // 验证最终数据一致
    consensus  = GET .../consensus
    divergence = GET .../divergence
    // 无重复 topic 条目
    topics_c = consensus.items.map(c => c.topic)
    topics_d = divergence.items.map(d => d.topic)
    assert new Set(topics_c).size == topics_c.length
    assert new Set(topics_d).size == topics_d.length
    // 每个条目的 latest_speech_id 指向有效的 speech
    all_ids = [s_a.id, s_b.id]
    for c in consensus.items:
      assert all_ids.includes(c.latest_speech_id) or
             c.latest_speech_id == null
```

---

## 附录：测试数据工厂

测试依赖可复用的种子数据，以下伪代码描述工厂方法（生产代码中实现）：

```
factory "seed_discussion"
  → POST /discussions { title, topic } → discussion_id

factory "seed_panelists"
  → POST /discussions/{id}/panelists/generate { count }
  → 返回 { host, experts[] }

factory "seed_full_discussion"
  → seed_discussion() + seed_panelists(count=5)
  → 返回 { discussion_id, host, experts }

factory "inject_speech"
  → 不走 DeepSeek，直接 INSERT INTO speeches
  → 返回 speech 对象 { id, discussion_id, panelist_id, content, sequence_num }

factory "trigger_consensus_analysis"
  → 调用内部分析函数（模块三测试专用桩）
  → 入参: discussion_id, latest_speech_id

factory "connect_sse"
  → new EventSource(GET /discussions/{id}/stream)
  → 返回事件收集器数组

helper "all_unique_within_similarity"
  → 对数组两两计算编辑距离 / 余弦相似度
  → 任意一对相似度 ≥ threshold → 不通过

helper "await_sse_event"
  → 阻塞等待指定 event 类型的 SSE 推送
  → 超时抛出 TIMEOUT

helper "mock_deepseek_timeout / mock_deepseek_response / mock_deepseek_streaming_timeout"
  → 测试专用 mock，拦截 DeepSeek 调用
  → 不实际消耗 API token
```

---

## 测试覆盖矩阵

| 模块 | 正常用例 | 边界用例 | 异常用例 | 合计 |
|---|---|---|---|---|
| 嘉宾自动生成 | 8 | 6 | 8 | **22** |
| AI 自主发言 | 9 | 6 | 9 | **24** |
| 共识分歧提取 | 10 | 8 | 6 | **24** |
| **总计** | **27** | **20** | **23** | **70** |
