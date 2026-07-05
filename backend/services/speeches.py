"""
AI Panel Studio — 发言服务
核心编排层：触发发言 → 流式生成 → SSE 推送 → 共识/分歧分析。
"""

import asyncio
import logging
import traceback
from datetime import datetime

from database import get_db, fetch_one, fetch_all, execute
from services.llm import (
    decide_next_speaker,
    generate_speech_stream,
    _validate_speech_length,
)
from services.consensus import trigger_consensus_analysis
from sse_manager import sse_manager

logger = logging.getLogger(__name__)

# 并发生成锁：同一讨论同一时间只允许一个发言生成中
_generating_locks: dict[int, asyncio.Lock] = {}
_generating_flags: dict[int, bool] = {}


def _ensure_lock(discussion_id: int) -> asyncio.Lock:
    """获取或创建讨论的生成锁。"""
    if discussion_id not in _generating_locks:
        _generating_locks[discussion_id] = asyncio.Lock()
    return _generating_locks[discussion_id]


async def trigger_next_speech(discussion_id: int, prompt_hint: str | None = None) -> dict:
    """
    触发下一轮 AI 发言（异步）。

    返回 202 确认后，后台执行:
    1. 决策下一位发言人
    2. 流式生成发言内容 → SSE 推送 speech.chunk
    3. 完整发言落库 → SSE 推送 speech.complete
    4. 触发共识/分歧分析 → SSE 推送 consensus.update / divergence.update

    Raises:
        ValueError: 讨论状态不合法
        RuntimeError: 并发生成冲突
    """
    db = await get_db()
    try:
        # ---- 校验讨论状态 ----
        discussion = await fetch_one(db, "SELECT * FROM discussions WHERE id = ?", (discussion_id,))
        if not discussion:
            raise ValueError("讨论不存在")
        if discussion["status"] == "completed":
            raise ValueError("讨论已结束，无法继续发言")
        if discussion["status"] == "paused":
            raise ValueError("讨论已暂停，请先恢复讨论")

        # ---- 校验嘉宾 ----
        panelists = await fetch_all(db, "SELECT * FROM panelists WHERE discussion_id = ?", (discussion_id,))
        if not panelists:
            raise ValueError("请先生成嘉宾阵容再开始讨论")
        experts = [p for p in panelists if p["role"] == "expert"]
        if not experts:
            raise ValueError("至少需要一位专家嘉宾才能开始讨论")

        # ---- 并发生成检查（对齐 TDD E2.5） ----
        lock = _ensure_lock(discussion_id)
        if _generating_flags.get(discussion_id, False):
            raise RuntimeError("当前已有发言正在生成中，请等待完成后再触发")

    finally:
        await db.close()

    # 异步启动生成流程
    asyncio.create_task(
        _background_generate_speech(discussion_id, panelists, prompt_hint)
    )

    return {
        "accepted": True,
        "message": "发言生成已启动，请通过 SSE 流获取内容",
        "estimated_seconds": 3.5,
    }


async def _background_generate_speech(
    discussion_id: int,
    panelists: list[dict],
    prompt_hint: str | None = None,
):
    """
    后台发言生成全流程（PRIVATE — 不直接对外暴露）。
    使用 asyncio.Lock 保证同一讨论同一时间只有一个生成任务。
    """
    lock = _ensure_lock(discussion_id)

    async with lock:
        # 二次检查（防止锁等待期间状态变化）
        if _generating_flags.get(discussion_id, False):
            logger.warning(f"[讨论{discussion_id}] 获取锁后发现已有生成任务，跳过")
            return

        _generating_flags[discussion_id] = True
        try:
            await _do_generate_speech(discussion_id, panelists, prompt_hint)
        except Exception as e:
            logger.error(f"[讨论{discussion_id}] 发言生成失败: {e}\n{traceback.format_exc()}")
            await sse_manager.broadcast_error(
                discussion_id, "AI_GENERATION_FAILED",
                "发言生成失败，请重试",
            )
        finally:
            _generating_flags[discussion_id] = False


async def _do_generate_speech(
    discussion_id: int,
    panelists: list[dict],
    prompt_hint: str | None = None,
):
    """执行发言生成的具体步骤。"""
    db = await get_db()
    try:
        discussion = await fetch_one(db, "SELECT * FROM discussions WHERE id = ?", (discussion_id,))
        if not discussion:
            return

        # ---- 获取上下文 ----
        recent_speeches = await fetch_all(
            db,
            "SELECT s.*, p.name AS panelist_name, p.color AS panelist_color, p.role AS panelist_role "
            "FROM speeches s LEFT JOIN panelists p ON s.panelist_id = p.id "
            "WHERE s.discussion_id = ? ORDER BY s.sequence_num ASC",
            (discussion_id,),
        )

        consensus = await fetch_all(
            db, "SELECT * FROM consensus_points WHERE discussion_id = ? ORDER BY updated_at DESC",
            (discussion_id,),
        )
        divergence = await fetch_all(
            db, "SELECT * FROM divergence_points WHERE discussion_id = ? ORDER BY updated_at DESC",
            (discussion_id,),
        )

        is_first_round = len(recent_speeches) == 0

        # ---- Step 1: 决策下一位发言人（对齐 TDD N2.1~N2.8） ----
        decision = await decide_next_speaker(
            discussion_topic=discussion["topic"] or discussion["title"],
            panelists=panelists,
            recent_speeches=recent_speeches,
            consensus_points=consensus,
            divergence_points=divergence,
            is_first_round=is_first_round,
            is_closing=False,
        )

        next_speaker_id = decision["next_speaker_id"]
        speech_type = decision["speech_type"]
        _internal_reason = decision.get("reason", "")  # 内部分析用，绝不输出

        speaker = next((p for p in panelists if p["id"] == next_speaker_id), None)
        if not speaker:
            logger.error(f"决策的发言人 ID={next_speaker_id} 不在嘉宾列表中")
            return

        logger.info(
            f"[讨论{discussion_id}] 下一位发言人: {speaker['name']} (ID={next_speaker_id}), "
            f"类型={speech_type}, 理由={_internal_reason}"
        )

        # ---- Step 2: 获取下一个 sequence_num ----
        max_seq_row = await fetch_one(
            db,
            "SELECT COALESCE(MAX(sequence_num), 0) AS max_seq FROM speeches WHERE discussion_id = ?",
            (discussion_id,),
        )
        next_seq = (max_seq_row["max_seq"] if max_seq_row else 0) + 1

        # ---- Step 3: 流式生成发言 → SSE 推送 chunk ----
        full_content = ""
        async for delta in generate_speech_stream(
            discussion_topic=discussion["topic"] or discussion["title"],
            speaker=speaker,
            speech_type=speech_type,
            all_panelists=panelists,
            recent_speeches=recent_speeches,
            consensus_points=consensus,
            divergence_points=divergence,
        ):
            full_content += delta
            # 推送流式 chunk（对齐 TDD N3.9 时序）
            await sse_manager.broadcast(discussion_id, "speech.chunk", {
                "sequence_num": next_seq,
                "panelist_id": next_speaker_id,
                "delta": delta,
            })

        # ---- Step 4: 内容清洗 + 落库 ----
        clean_content = _validate_speech_length(full_content)

        if not clean_content.strip():
            logger.warning(f"生成发言为空，丢弃。原始内容: {full_content[:100]}")
            await sse_manager.broadcast_error(discussion_id, "EMPTY_SPEECH", "生成的发言内容为空，请重试")
            return

        speech_id = await execute(
            db,
            """INSERT INTO speeches (discussion_id, panelist_id, content, sequence_num)
               VALUES (?, ?, ?, ?)""",
            (discussion_id, next_speaker_id, clean_content, next_seq),
        )

        # 更新时间戳
        now_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        await execute(
            db,
            "UPDATE discussions SET updated_at = datetime('now', 'localtime') WHERE id = ?",
            (discussion_id,),
        )

        # ---- Step 5: SSE 推送完整发言 ----
        speech_obj = {
            "id": speech_id,
            "discussion_id": discussion_id,
            "panelist_id": next_speaker_id,
            "panelist_name": speaker["name"],
            "panelist_color": speaker.get("color", "#3388FF"),
            "content": clean_content,
            "sequence_num": next_seq,
            "created_at": now_str,
        }
        await sse_manager.broadcast(discussion_id, "speech.complete", speech_obj)

        # 更新 recent_speeches 供后续分析使用
        recent_speeches.append(speech_obj)

        # ---- Step 6: 触发共识/分歧分析（对齐 TDD N3.1~N3.9） ----
        await trigger_consensus_analysis(
            db=db,
            discussion_id=discussion_id,
            discussion_topic=discussion["topic"] or discussion["title"],
            new_speech=speech_obj,
            all_panelists=panelists,
            all_speeches=recent_speeches,
        )

    finally:
        await db.close()


async def list_speeches(
    discussion_id: int,
    after_sequence: int | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """查询发言列表。"""
    db = await get_db()
    try:
        where = "WHERE s.discussion_id = ?"
        params: list = [discussion_id]

        if after_sequence is not None:
            where += " AND s.sequence_num > ?"
            params.append(after_sequence)

        count_row = await fetch_one(
            db,
            f"SELECT COUNT(*) AS total FROM speeches s {where}",
            tuple(params),
        )
        total = count_row["total"] if count_row else 0

        offset = (page - 1) * page_size
        rows = await fetch_all(
            db,
            f"""SELECT s.*,
                       COALESCE(p.name, '(已离场嘉宾)') AS panelist_name,
                       COALESCE(p.color, '#95A5A6') AS panelist_color
                FROM speeches s
                LEFT JOIN panelists p ON s.panelist_id = p.id
                {where}
                ORDER BY s.sequence_num ASC
                LIMIT ? OFFSET ?""",
            tuple(params + [page_size, offset]),
        )
        return {"items": rows, "total": total}
    finally:
        await db.close()
