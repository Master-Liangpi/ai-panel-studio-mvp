"""
AI Panel Studio — LLM 服务层（PRIVATE）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
所有 DeepSeek 大模型调用逻辑封装在此模块内，路由层绝不直接调用。
密钥仅从 config.DEEPSEEK_API_KEY 读取，不通过任何接口参数传入。
所有 prompt 工程、响应解析、内容过滤集中管理。

四大核心能力:
  1. generate_panelists   — 自动生成嘉宾阵容
  2. decide_next_speaker  — 模拟举手/抢答/补充/反驳，决策下一位发言人
  3. generate_speech_stream — 为指定嘉宾流式生成发言
  4. analyze_consensus_divergence — 增量提取共识与分歧
  5. generate_summary     — 生成圆桌收尾总结
"""

import json
import logging
import re
from typing import AsyncGenerator

import httpx

from config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    DEEPSEEK_TIMEOUT,
    DEEPSEEK_STREAM_TIMEOUT,
    SPEECH_MIN_CHARS,
    SPEECH_MAX_CHARS,
)

logger = logging.getLogger(__name__)

# ============================================================
# 内部常量
# ============================================================

CHAT_URL = f"{DEEPSEEK_BASE_URL.rstrip('/')}/v1/chat/completions"

# 内部分析用（绝不输出到前端）
_SPEECH_TYPES = ["opening", "rebuttal", "supplement", "new_point", "transition", "closing"]

# ============================================================
# 底层 HTTP 调用（PRIVATE — 模块内部使用）
# ============================================================

async def _call_deepseek(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 2048,
    response_json: bool = False,
) -> str:
    """
    PRIVATE: 非流式调用 DeepSeek Chat API，返回完整响应文本。

    Args:
        messages: 标准 OpenAI 格式消息列表
        temperature: 采样温度
        max_tokens: 最大输出 token
        response_json: 是否要求 JSON 格式输出

    Returns:
        模型响应文本

    Raises:
        httpx.HTTPError: 网络/API 错误
        ValueError: 响应解析失败
    """
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY 未配置")

    body = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if response_json:
        body["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=DEEPSEEK_TIMEOUT) as client:
        response = await client.post(CHAT_URL, json=body, headers=headers)
        response.raise_for_status()
        result = response.json()

    try:
        content = result["choices"][0]["message"]["content"]
        return content
    except (KeyError, IndexError) as e:
        logger.error(f"DeepSeek 响应结构异常: {result}")
        raise ValueError(f"无法解析 DeepSeek 响应: {e}")


async def _stream_deepseek(
    messages: list[dict],
    temperature: float = 0.8,
    max_tokens: int = 512,
) -> AsyncGenerator[str, None]:
    """
    PRIVATE: 流式调用 DeepSeek Chat API，逐 token 产出文本。

    Yields:
        增量文本片段 (delta content)
    """
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY 未配置")

    body = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=DEEPSEEK_STREAM_TIMEOUT) as client:
        async with client.stream("POST", CHAT_URL, json=body, headers=headers) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk["choices"][0].get("delta", {})
                    if "content" in delta:
                        yield delta["content"]
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue


# ============================================================
# 内容过滤（PRIVATE）
# ============================================================

def _sanitize_content(text: str) -> str:
    """
    PRIVATE: 过滤模型输出中的内部标记和原始数据。

    移除:
      - "---DECISION---" / "---SPEECH---" 等内部分隔符
      - JSON 结构残留（{...}）
      - "DeepSeek" / "deepseek" 模型名称
      - 系统 prompt 残留（"system:", "user:", "assistant:"）
      - 思考链标记（"嗯"、"[思考]"、"[internal]" 等约定标记）
    """
    # 移除内部分隔符及后续内容
    text = re.sub(r'---+?\s*(DECISION|SPEECH|INTERNAL|ANALYSIS)\s*---+?.*', '', text, flags=re.IGNORECASE)

    # 移除 JSON 块
    text = re.sub(r'\{[^{}]*"next_speaker_id"[^{}]*\}', '', text)
    text = re.sub(r'\{[^{}]*"action"[^{}]*\}', '', text)

    # 移除模型/系统标记
    text = re.sub(r'\b(DeepSeek|deepseek|OpenAI|openai|ChatGPT)\b', '', text)
    text = re.sub(r'\b(system:|user:|assistant:|human:|ai:)\s*', '', text, flags=re.IGNORECASE)

    # 移除思考标记
    text = re.sub(r'\[(思考|内部|internal|思考链|CoT|chain.of.thought)\][^\n]*', '', text, flags=re.IGNORECASE)

    # 清理多余空白
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    return text


def _validate_speech_length(content: str) -> str:
    """
    PRIVATE: 校验发言长度。过短或过长时截断/告警。
    """
    content = _sanitize_content(content)
    char_count = len(content)

    if char_count < SPEECH_MIN_CHARS:
        logger.warning(f"发言过短 ({char_count} 字)，内容: {content[:50]}...")
        # 不丢弃，记录告警（可能是模型输出的简短肯定/否定）
    if char_count > SPEECH_MAX_CHARS:
        logger.warning(f"发言过长 ({char_count} 字)，截断至 {SPEECH_MAX_CHARS} 字")
        # 智能截断：在最后一个完整句子处断开
        truncated = content[:SPEECH_MAX_CHARS]
        last_period = max(truncated.rfind("。"), truncated.rfind("！"), truncated.rfind("？"))
        if last_period > SPEECH_MAX_CHARS // 2:
            content = truncated[:last_period + 1]
        else:
            content = truncated + "。"

    return content


# ============================================================
# 1. 嘉宾阵容生成
# ============================================================

PANELIST_GENERATION_SYSTEM = """你是一位资深的圆桌讨论策划人。根据给定话题，你需要生成一组多元化的讨论嘉宾。

核心要求:
1. 生成恰好 {count} 位嘉宾，其中 1 位主持人(role="host") + {expert_count} 位专家(role="expert")
2. 每位嘉宾的立场(stance)必须互不相同，覆盖支持、反对、中立等多元视角
3. 每位嘉宾的职业头衔(title)必须互不相同
4. 每位嘉宾的标识色(color)必须互不相同，使用高对比度、视觉可区分的 Hex 色值
5. 主持人立场应为中立客观，负责引导讨论
6. 姓名使用中文（2-4 字）

输出严格的 JSON 格式，不要包含任何额外文字:
{
  "host": {
    "name": "主持人姓名",
    "title": "职业头衔",
    "stance": "中立立场描述",
    "color": "#HEX色值"
  },
  "experts": [
    {
      "name": "专家姓名",
      "title": "职业头衔",
      "stance": "明确立场描述（必须与其他专家不同）",
      "color": "#HEX色值"
    }
  ]
}
"""


async def generate_panelists(topic: str, count: int) -> dict:
    """
    根据话题自动生成嘉宾阵容。

    Args:
        topic: 讨论议题
        count: 嘉宾总数（含主持人）

    Returns:
        {"host": {...}, "experts": [{...}, ...]}

    Raises:
        ValueError: 人数不合法
        RuntimeError: AI 生成失败
    """
    expert_count = count - 1
    system_prompt = (
        PANELIST_GENERATION_SYSTEM
        .replace("{count}", str(count))
        .replace("{expert_count}", str(expert_count))
    )
    user_prompt = f"话题：{topic}\n\n请生成 {count} 位嘉宾（1 位主持人 + {expert_count} 位专家）。"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    raw_response = await _call_deepseek(messages, temperature=0.7, max_tokens=4096, response_json=True)

    try:
        result = json.loads(raw_response)
    except json.JSONDecodeError:
        # 尝试从响应中提取 JSON 块
        match = re.search(r'\{[\s\S]*\}', raw_response)
        if match:
            try:
                result = json.loads(match.group())
            except json.JSONDecodeError:
                raise RuntimeError("DeepSeek 返回的内容无法解析为 JSON")
        else:
            raise RuntimeError("DeepSeek 返回的内容无法解析为 JSON")

    # 校验返回结构
    if "host" not in result or "experts" not in result:
        raise RuntimeError("DeepSeek 返回的嘉宾数据缺少 host 或 experts 字段")

    experts = result["experts"]
    if len(experts) != expert_count:
        logger.warning(f"DeepSeek 返回 {len(experts)} 位专家，期望 {expert_count}，以实际为准")

    # 后置校验：去重
    _ensure_unique_stances(result)
    _ensure_unique_colors(result)

    return result


def _ensure_unique_stances(result: dict):
    """确保所有嘉宾立场唯一（相似度检测）。"""
    all_stances = [result["host"]["stance"]] + [e["stance"] for e in result["experts"]]
    for i, s1 in enumerate(all_stances):
        for j, s2 in enumerate(all_stances):
            if i >= j:
                continue
            similarity = _text_similarity(s1, s2)
            if similarity > 0.7:
                logger.warning(f"立场 {i} 与 {j} 相似度过高 ({similarity:.2f})，添加区分标记")
                # 为较短的立场添加区分后缀
                if len(s1) <= len(s2):
                    result["host" if i == 0 else "experts"][i - 1 if i > 0 else 0]["stance"] += "（侧重不同维度）"
                else:
                    idx = j - 1 if j > 0 else 0
                    target = result["host"] if j == 0 else result["experts"][idx]
                    target["stance"] += "（侧重不同维度）"


def _ensure_unique_colors(result: dict):
    """确保所有嘉宾颜色唯一。"""
    all_colors = [result["host"]["color"]] + [e["color"] for e in result["experts"]]
    seen = set()
    for i, c in enumerate(all_colors):
        c_upper = c.upper()
        if c_upper in seen:
            # 分配备用颜色
            fallback_colors = [
                "#E74C3C", "#3498DB", "#2ECC71", "#F39C12", "#9B59B6",
                "#1ABC9C", "#E67E22", "#2980B9", "#C0392B", "#27AE60",
            ]
            for fb in fallback_colors:
                if fb not in seen:
                    if i == 0:
                        result["host"]["color"] = fb
                    else:
                        result["experts"][i - 1]["color"] = fb
                    seen.add(fb)
                    break
        else:
            seen.add(c_upper)


def _text_similarity(a: str, b: str) -> float:
    """简单的文本相似度（基于共同字符比例）。"""
    a_set = set(a)
    b_set = set(b)
    if not a_set or not b_set:
        return 0.0
    intersection = a_set & b_set
    return len(intersection) / min(len(a_set), len(b_set))


# ============================================================
# 2. 下一位发言者决策
# ============================================================

SPEAKER_DECISION_SYSTEM = """你是圆桌讨论的调度导演。根据当前讨论状态，决定下一位发言人。

决策规则（必须遵守）:
1. 绝对不要固定轮流发言——模拟真实圆桌的随机性
2. 发言类型: opening(开场), rebuttal(反驳), supplement(补充), new_point(新观点), transition(串场), closing(收尾)
3. 如果上一轮有人表达了争议性观点，优先选持相反立场的嘉宾进行"反驳"
4. 如果上一轮有人表达了某种立场，优先选立场相近的嘉宾进行"补充"
5. 连续 3 次专家发言后，第 4 次应由主持人"串场"
6. 第一轮必须由主持人"开场"（opening）
7. 不要连续选同一个人（除非只有 2 位嘉宾时除外，但同一个人连续不超过 2 次）
8. 优先选择近期未发言的嘉宾

输出严格的 JSON 格式:
{
  "next_speaker_id": <嘉宾数据库ID>,
  "speech_type": "<opening|rebuttal|supplement|new_point|transition|closing>",
  "reason": "<内部决策理由，不超过20字>"
}
"reason" 字段仅供内部调度使用，绝不能出现在发言内容中。"""


async def decide_next_speaker(
    discussion_topic: str,
    panelists: list[dict],
    recent_speeches: list[dict],
    consensus_points: list[dict],
    divergence_points: list[dict],
    is_first_round: bool = False,
    is_closing: bool = False,
) -> dict:
    """
    决定下一位发言人。

    Args:
        discussion_topic: 讨论议题
        panelists: 嘉宾列表 [{id, name, role, stance, title}, ...]
        recent_speeches: 最近发言（最多 15 条）
        consensus_points: 当前共识列表
        divergence_points: 当前分歧列表
        is_first_round: 是否第一轮（必须主持人开场）
        is_closing: 是否收尾（必须主持人收尾）

    Returns:
        {"next_speaker_id": int, "speech_type": str, "reason": str}
    """
    # 构建上下文
    host = next((p for p in panelists if p["role"] == "host"), None)

    if is_first_round and host:
        return {
            "next_speaker_id": host["id"],
            "speech_type": "opening",
            "reason": "首轮由主持人开场",
        }
    if is_closing and host:
        return {
            "next_speaker_id": host["id"],
            "speech_type": "closing",
            "reason": "讨论收尾由主持人总结",
        }

    # 构建决策 prompt
    panelist_desc = "\n".join(
        f"- ID={p['id']} | {p['name']} | 角色={p['role']} | 立场={p['stance']} | 头衔={p['title']}"
        for p in panelists
    )

    speech_history = "（尚无发言）"
    if recent_speeches:
        lines = []
        for s in recent_speeches[-15:]:
            name = s.get("panelist_name", f"嘉宾{s['panelist_id']}")
            lines.append(f"#{s['sequence_num']} [{name}]: {s['content'][:100]}")
        speech_history = "\n".join(lines)

    consensus_desc = "暂无共识" if not consensus_points else "\n".join(
        f"- [{c['topic']}] {c['content'][:80]}" for c in consensus_points
    )
    divergence_desc = "暂无分歧" if not divergence_points else "\n".join(
        f"- [{d['topic']}] {d['content'][:80]}" for d in divergence_points
    )

    user_prompt = f"""讨论议题: {discussion_topic}

=== 嘉宾阵容 ===
{panelist_desc}

=== 最近发言记录 ===
{speech_history}

=== 已有共识 ===
{consensus_desc}

=== 已有分歧 ===
{divergence_desc}

请决定下一位发言人。"""

    messages = [
        {"role": "system", "content": SPEAKER_DECISION_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]

    raw = await _call_deepseek(messages, temperature=0.9, max_tokens=512, response_json=True)

    try:
        decision = json.loads(raw)
        # 校验必需字段
        if "next_speaker_id" not in decision:
            raise ValueError("缺少 next_speaker_id")
        # 校验 speaker_id 有效
        valid_ids = {p["id"] for p in panelists}
        if decision["next_speaker_id"] not in valid_ids:
            logger.warning(f"DeepSeek 返回无效 speaker_id={decision['next_speaker_id']}，回退到主持人")
            decision["next_speaker_id"] = host["id"] if host else panelists[0]["id"]
        return decision
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"发言者决策解析失败: {e}, raw={raw[:200]}")
        # 安全回退：选最近未发言的 expert
        recent_speaker_ids = [s["panelist_id"] for s in recent_speeches[-5:]]
        for p in panelists:
            if p["id"] not in recent_speaker_ids and p["role"] == "expert":
                return {"next_speaker_id": p["id"], "speech_type": "new_point", "reason": "回退策略：选最近未发言专家"}
        # 最终回退到主持人
        if host:
            return {"next_speaker_id": host["id"], "speech_type": "transition", "reason": "回退策略：主持人"}
        return {"next_speaker_id": panelists[0]["id"], "speech_type": "new_point", "reason": "回退策略：第一位嘉宾"}


# ============================================================
# 3. 发言内容生成（流式）
# ============================================================

SPEECH_GENERATION_SYSTEM = """你是圆桌讨论中的一位嘉宾。现在轮到你发言。

发言规则:
1. 控制在 1-2 句话（{min_chars}-{max_chars} 个中文字符）
2. 内容必须符合你的立场和身份
3. 如果是反驳: 先简要承认对方观点的合理之处，再提出不同看法，语气保持尊重
4. 如果是补充: 在赞同基础上添加新论据或新角度，不要简单重复
5. 如果是新观点: 提出此前未被提及的维度
6. 如果是串场/收尾: 主持人总结前文要点，自然过渡
7. 使用口头化的中文表达，不要像写论文
8. 绝对不要输出 JSON、代码块、或任何结构化格式——只输出纯文本发言
9. 不要输出"（思考）""（停顿）"等舞台指示"""


async def generate_speech_stream(
    discussion_topic: str,
    speaker: dict,
    speech_type: str,
    all_panelists: list[dict],
    recent_speeches: list[dict],
    consensus_points: list[dict],
    divergence_points: list[dict],
) -> AsyncGenerator[str, None]:
    """
    流式生成嘉宾发言内容。

    Args:
        discussion_topic: 讨论议题
        speaker: 当前发言人 {id, name, role, stance, title}
        speech_type: 发言类型
        all_panelists: 全部嘉宾
        recent_speeches: 最近发言
        consensus_points: 当前共识
        divergence_points: 当前分歧

    Yields:
        增量文本片段
    """
    other_panelists = [p for p in all_panelists if p["id"] != speaker["id"]]
    other_desc = "\n".join(
        f"- {p['name']}（{p['role']}）：{p['stance']}"
        for p in other_panelists
    )

    recent_desc = "（尚无发言）"
    if recent_speeches:
        recent_desc = "\n".join(
            f"[{s.get('panelist_name', '嘉宾')}]: {s['content']}"
            for s in recent_speeches[-10:]
        )

    consensus_desc = "暂无" if not consensus_points else "; ".join(
        f"{c['topic']}: {c['content'][:50]}" for c in consensus_points
    )
    divergence_desc = "暂无" if not divergence_points else "; ".join(
        f"{d['topic']}: {d['content'][:50]}" for d in divergence_points
    )

    # 构建发言角色提示
    role_guidance = _build_role_guidance(speech_type, speaker["role"])

    system_prompt = SPEECH_GENERATION_SYSTEM.format(
        min_chars=SPEECH_MIN_CHARS,
        max_chars=SPEECH_MAX_CHARS,
    )

    user_prompt = f"""讨论议题: {discussion_topic}

=== 你的身份 ===
姓名: {speaker['name']}
角色: {speaker['role']}（{'主持人' if speaker['role'] == 'host' else '专家'}）
立场: {speaker['stance']}
头衔: {speaker['title']}

=== 其他嘉宾 ===
{other_desc}

=== 最近发言 ===
{recent_desc}

=== 当前共识 ===
{consensus_desc}

=== 当前分歧 ===
{divergence_desc}

=== 本轮要求 ===
{role_guidance}

请以 {speaker['name']} 的身份发言——只输出纯文本发言内容，不要加任何格式标记："""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    async for delta in _stream_deepseek(messages, temperature=0.85, max_tokens=512):
        yield delta


def _build_role_guidance(speech_type: str, role: str) -> str:
    """构建发言角色提示（内部分析用，不输出到前端）。"""
    guidance = {
        "opening": "这是讨论的开场白。请以主持人身份欢迎嘉宾、介绍议题、抛出第一个讨论方向。不要输出 JSON 格式。",
        "rebuttal": "你需要礼貌地反驳上一位发言者的核心观点。先肯定对方的合理之处，再提出你的不同看法和论据。不要输出 JSON 格式。",
        "supplement": "你需要补充支持上一位发言者的观点。在赞同基础上，加入新的论据、数据或角度——不要简单重复对方的话。不要输出 JSON 格式。",
        "new_point": "你需要提出一个全新的讨论角度，之前没有人提到过。这个角度应与你的立场一致。不要输出 JSON 格式。",
        "transition": "你是主持人。需要总结最近几轮的观点碰撞，然后引导讨论进入下一个子议题或邀请另一位嘉宾发言。不要输出 JSON 格式。",
        "closing": "你是主持人。做整场讨论的收尾总结——概括核心共识和主要分歧，感谢所有嘉宾的参与。不要输出 JSON 格式。",
    }
    return guidance.get(speech_type, "请根据你的立场和当前讨论进展，做出自然、通顺的发言。不要输出 JSON 格式。")


# ============================================================
# 4. 共识 & 分歧分析
# ============================================================

CONSENSUS_ANALYSIS_SYSTEM = """你是一位中立的讨论分析员。根据最新一句发言，分析是否需要新增或更新共识点和分歧点。

分析规则:
1. 只关注实质性观点——空话、客套话、过渡串场不产生任何更新
2. 当 2 位及以上嘉宾表达了相同或高度相近的观点时，形成一个"共识"
3. 当 2 位及以上嘉宾在某个问题上立场明显对立时，形成一个"分歧"
4. 如果新发言强化了已有共识/分歧——更新该条目（追加发言人），不要重复创建
5. 如果新发言中某位嘉宾改变了之前立场、接受了对方观点——该分歧标记为"resolve"
6. 多条发言指向同一共识/分歧时，合并为一条
7. topic 必须精炼（≤20 字），content 必须用自然语言描述（不要引用嘉宾原话）
8. sides 字段格式: "A方立场：嘉宾A、嘉宾B / B方立场：嘉宾C"

输出严格的 JSON 格式:
{
  "consensus_updates": [
    {"action": "create", "topic": "共识主题", "content": "共识内容描述", "speaker_ids": [1, 2]},
    {"action": "update", "id": 3, "topic": "更新后的主题", "content": "更新后的内容", "speaker_ids": [1, 2, 3]}
  ],
  "divergence_updates": [
    {"action": "create", "topic": "分歧主题", "content": "分歧内容描述", "sides": "A方：张三 / B方：李四"},
    {"action": "update", "id": 2, "topic": "更新后的主题", "content": "更新后的内容", "sides": "A方：张三、王五 / B方：李四"},
    {"action": "resolve", "id": 2}
  ]
}
如果本轮发言没有触发任何更新，返回:
{"consensus_updates": [], "divergence_updates": []}"""


async def analyze_consensus_divergence(
    discussion_topic: str,
    new_speech: dict,
    all_panelists: list[dict],
    all_speeches: list[dict],
    existing_consensus: list[dict],
    existing_divergence: list[dict],
) -> dict:
    """
    分析最新发言，返回共识和分歧的增量更新。

    Args:
        discussion_topic: 讨论议题
        new_speech: 最新发言 {id, panelist_id, panelist_name, content, sequence_num}
        all_panelists: 全部嘉宾
        all_speeches: 全部发言
        existing_consensus: 已有共识
        existing_divergence: 已有分歧

    Returns:
        {"consensus_updates": [...], "divergence_updates": [...]}
    """
    # 空发言不分析
    if not new_speech.get("content", "").strip():
        logger.info(f"发言 #{new_speech.get('sequence_num')} 为空，跳过共识/分歧分析")
        return {"consensus_updates": [], "divergence_updates": []}

    # 只有一句发言时（无比较基准），不分析
    if len(all_speeches) <= 1:
        logger.info("仅有 1 条发言，无比较基准，跳过分析")
        return {"consensus_updates": [], "divergence_updates": []}

    # 只有一位专家发言时，不分析
    expert_count = sum(1 for p in all_panelists if p["role"] == "expert")
    expert_speeches = [s for s in all_speeches
                       if any(p["id"] == s["panelist_id"] and p["role"] == "expert"
                              for p in all_panelists)]
    if expert_count < 2 or len(expert_speeches) < 2:
        logger.info("少于 2 位专家发言，跳过分析")
        return {"consensus_updates": [], "divergence_updates": []}

    # 构建分析上下文
    panelist_map = {p["id"]: p for p in all_panelists}

    panelist_desc = "\n".join(
        f"ID={p['id']} {p['name']}（{p['role']}）立场={p['stance']}"
        for p in all_panelists
    )

    speech_lines = []
    for s in all_speeches:
        panelist_name = s.get("panelist_name") or f"ID:{s['panelist_id']}"
        speech_lines.append(f"#{s['sequence_num']} [{panelist_name}]: {s['content']}")
    speech_desc = "\n".join(speech_lines)

    consensus_desc = "暂无" if not existing_consensus else "\n".join(
        f"共识#{c['id']} [{c['topic']}]: {c['content']} (涉及嘉宾: {c.get('involved_speaker_ids', '')})"
        for c in existing_consensus
    )

    divergence_desc = "暂无" if not existing_divergence else "\n".join(
        f"分歧#{d['id']} [{d['topic']}]: {d['content']} | sides: {d['sides']}"
        for d in existing_divergence
    )

    user_prompt = f"""讨论议题: {discussion_topic}

=== 嘉宾信息 ===
{panelist_desc}

=== 全部发言记录 ===
{speech_desc}

=== 已有共识 ===
{consensus_desc}

=== 已有分歧 ===
{divergence_desc}

=== 最新发言（需要分析） ===
#{new_speech['sequence_num']} [{new_speech.get('panelist_name', '嘉宾')}]: {new_speech['content']}

请分析并返回共识/分歧更新。"""

    messages = [
        {"role": "system", "content": CONSENSUS_ANALYSIS_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]

    raw = await _call_deepseek(messages, temperature=0.2, max_tokens=4096, response_json=True)

    try:
        result = json.loads(raw)
        if "consensus_updates" not in result:
            result["consensus_updates"] = []
        if "divergence_updates" not in result:
            result["divergence_updates"] = []
        return result
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            try:
                result = json.loads(match.group())
                result.setdefault("consensus_updates", [])
                result.setdefault("divergence_updates", [])
                return result
            except json.JSONDecodeError:
                pass
        logger.error(f"共识/分歧分析 JSON 解析失败，返回空: {raw[:200]}")
        return {"consensus_updates": [], "divergence_updates": []}


# ============================================================
# 5. 收尾总结
# ============================================================

SUMMARY_SYSTEM = """你是一位专业的圆桌讨论记录员。请根据整场讨论的全部发言、共识和分歧，生成一份 Markdown 格式的讨论总结。

总结结构:
## 讨论概述
（2-3 句话概括整场讨论的核心议题和讨论脉络）

## 核心共识
（列出所有达成的共识，每条共识用粗体标题 + 1-2 句描述）

## 主要分歧
（列出仍然存在的分歧，每条分启用粗体标题 + 各方立场简述）

## 讨论亮点
（摘录 2-3 个精彩的发言片段或观点碰撞，不做评价）

## 后续建议
（基于讨论内容，提出 2-3 条后续值得深入探讨的方向）

格式要求:
- 使用 Markdown 标准语法（## ### ** - 等）
- 语言自然、客观，不添加主观评价
- 不提及任何 AI 模型、DeepSeek、系统 prompt 信息
- 不输出 JSON 结构
- 不要输出"以下是一份总结"等开场白——直接从"## 讨论概述"开始"""


async def generate_summary(
    discussion_topic: str,
    all_speeches: list[dict],
    consensus_points: list[dict],
    divergence_points: list[dict],
    panelists: list[dict],
) -> str:
    """
    生成 Markdown 格式的讨论收尾总结。

    Args:
        discussion_topic: 讨论议题
        all_speeches: 全部发言
        consensus_points: 全部共识
        divergence_points: 全部分歧
        panelists: 全部嘉宾

    Returns:
        Markdown 格式的总结全文
    """
    speech_text = "\n".join(
        f"#{s['sequence_num']} [{s.get('panelist_name', '嘉宾')}（{s.get('panelist_role', '')}）]: {s['content']}"
        for s in all_speeches
    )

    consensus_text = "无" if not consensus_points else "\n".join(
        f"- [{c['topic']}] {c['content']}" for c in consensus_points
    )

    divergence_text = "无" if not divergence_points else "\n".join(
        f"- [{d['topic']}] {d['content']}（立场的对立：{d['sides']}）"
        for d in divergence_points
    )

    panelist_text = "\n".join(
        f"- {p['name']}（{p['title']}）：{p['stance']}"
        for p in panelists
    )

    user_prompt = f"""讨论议题: {discussion_topic}

=== 嘉宾阵容 ===
{panelist_text}

=== 全部发言（共 {len(all_speeches)} 条） ===
{speech_text}

=== 形成的共识 ===
{consensus_text}

=== 存在的分歧 ===
{divergence_text}

请生成讨论总结。直接从"## 讨论概述"开始写，不要加任何开场白："""

    messages = [
        {"role": "system", "content": SUMMARY_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]

    raw = await _call_deepseek(messages, temperature=0.4, max_tokens=4096)

    # 内容清洗：移除可能的 JSON 残留和内部分析标记
    summary = _sanitize_content(raw)

    # 确保以 "##" 开头
    if not summary.startswith("##"):
        summary = "## 讨论概述\n\n" + summary

    return summary
