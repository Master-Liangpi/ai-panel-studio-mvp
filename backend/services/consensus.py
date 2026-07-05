"""
AI Panel Studio — 共识 & 分歧服务
每一条新发言触发增量分析，结果通过 SSE 实时推送。
"""

import logging
from datetime import datetime

import aiosqlite

from database import fetch_one, fetch_all, execute
from services.llm import analyze_consensus_divergence
from sse_manager import sse_manager

logger = logging.getLogger(__name__)


async def trigger_consensus_analysis(
    db: aiosqlite.Connection,
    discussion_id: int,
    discussion_topic: str,
    new_speech: dict,
    all_panelists: list[dict],
    all_speeches: list[dict],
) -> None:
    """
    触发共识 & 分歧分析（在发言落库后调用）。

    流程:
    1. 调用 DeepSeek 分析
    2. 根据返回的 updates 增/改/删共识和分歧行
    3. 通过 SSE 推送变更
    """
    existing_consensus = await fetch_all(
        db,
        "SELECT * FROM consensus_points WHERE discussion_id = ? ORDER BY updated_at DESC",
        (discussion_id,),
    )
    existing_divergence = await fetch_all(
        db,
        "SELECT * FROM divergence_points WHERE discussion_id = ? ORDER BY updated_at DESC",
        (discussion_id,),
    )

    try:
        analysis = await analyze_consensus_divergence(
            discussion_topic=discussion_topic,
            new_speech=new_speech,
            all_panelists=all_panelists,
            all_speeches=all_speeches,
            existing_consensus=existing_consensus,
            existing_divergence=existing_divergence,
        )
    except Exception as e:
        logger.error(f"共识/分歧分析调用失败 discussion={discussion_id}: {e}")
        # 不推送 error 事件——发言已成功，仅分析失败，不影响用户体验
        return

    now_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # ---- 处理共识更新 ----
    for update in analysis.get("consensus_updates", []):
        try:
            action = update.get("action", "")
            if action == "create":
                await _create_consensus(db, discussion_id, update, new_speech["id"], now_str)
            elif action == "update":
                await _update_consensus(db, discussion_id, update, new_speech["id"], now_str)
            else:
                logger.warning(f"未知的共识 action: {action}")
        except Exception as e:
            logger.error(f"处理共识更新失败: {e}, update={update}")

    # ---- 处理分歧更新 ----
    for update in analysis.get("divergence_updates", []):
        try:
            action = update.get("action", "")
            if action == "create":
                await _create_divergence(db, discussion_id, update, new_speech["id"], now_str)
            elif action == "update":
                await _update_divergence(db, discussion_id, update, new_speech["id"], now_str)
            elif action == "resolve":
                await _resolve_divergence(db, discussion_id, update)
            else:
                logger.warning(f"未知的分歧 action: {action}")
        except Exception as e:
            logger.error(f"处理分歧更新失败: {e}, update={update}")


async def _create_consensus(db, discussion_id: int, update: dict, speech_id: int, now_str: str):
    """创建新共识并推送 SSE。"""
    topic = update.get("topic", "")
    content = update.get("content", "")
    if not topic or not content:
        return

    cid = await execute(
        db,
        """INSERT INTO consensus_points (discussion_id, topic, content, latest_speech_id)
           VALUES (?, ?, ?, ?)""",
        (discussion_id, topic, content, speech_id),
    )
    row = await fetch_one(db, "SELECT * FROM consensus_points WHERE id = ?", (cid,))
    if row:
        await sse_manager.broadcast(discussion_id, "consensus.update", dict(row))
        logger.info(f"[讨论{discussion_id}] 新增共识 #{cid}: {topic}")


async def _update_consensus(db, discussion_id: int, update: dict, speech_id: int, now_str: str):
    """更新已有共识并推送 SSE。"""
    cid = update.get("id")
    topic = update.get("topic", "")
    content = update.get("content", "")
    if not cid or (not topic and not content):
        return

    # 只更新有值的字段
    set_parts = ["latest_speech_id = ?", "updated_at = datetime('now', 'localtime')"]
    params: list = [speech_id]
    if topic:
        set_parts.append("topic = ?")
        params.append(topic)
    if content:
        set_parts.append("content = ?")
        params.append(content)
    params.append(discussion_id)
    params.append(cid)

    await execute(
        db,
        f"UPDATE consensus_points SET {', '.join(set_parts)} WHERE discussion_id = ? AND id = ?",
        tuple(params),
    )
    row = await fetch_one(db, "SELECT * FROM consensus_points WHERE id = ?", (cid,))
    if row:
        await sse_manager.broadcast(discussion_id, "consensus.update", dict(row))
        logger.info(f"[讨论{discussion_id}] 更新共识 #{cid}: {topic}")


async def _create_divergence(db, discussion_id: int, update: dict, speech_id: int, now_str: str):
    """创建新分歧并推送 SSE。"""
    topic = update.get("topic", "")
    content = update.get("content", "")
    sides = update.get("sides", "")
    if not topic or not content:
        return

    did = await execute(
        db,
        """INSERT INTO divergence_points (discussion_id, topic, content, sides, latest_speech_id)
           VALUES (?, ?, ?, ?, ?)""",
        (discussion_id, topic, content, sides, speech_id),
    )
    row = await fetch_one(db, "SELECT * FROM divergence_points WHERE id = ?", (did,))
    if row:
        await sse_manager.broadcast(discussion_id, "divergence.update", dict(row))
        logger.info(f"[讨论{discussion_id}] 新增分歧 #{did}: {topic}")


async def _update_divergence(db, discussion_id: int, update: dict, speech_id: int, now_str: str):
    """更新已有分歧并推送 SSE。"""
    did = update.get("id")
    topic = update.get("topic", "")
    content = update.get("content", "")
    sides = update.get("sides", "")
    if not did:
        return

    set_parts = ["latest_speech_id = ?", "updated_at = datetime('now', 'localtime')"]
    params: list = [speech_id]
    if topic:
        set_parts.append("topic = ?")
        params.append(topic)
    if content:
        set_parts.append("content = ?")
        params.append(content)
    if sides:
        set_parts.append("sides = ?")
        params.append(sides)
    params.append(discussion_id)
    params.append(did)

    await execute(
        db,
        f"UPDATE divergence_points SET {', '.join(set_parts)} WHERE discussion_id = ? AND id = ?",
        tuple(params),
    )
    row = await fetch_one(db, "SELECT * FROM divergence_points WHERE id = ?", (did,))
    if row:
        await sse_manager.broadcast(discussion_id, "divergence.update", dict(row))
        logger.info(f"[讨论{discussion_id}] 更新分歧 #{did}: {topic}")


async def _resolve_divergence(db, discussion_id: int, update: dict):
    """删除已解决的分歧并推送 SSE（通过 broadcast 标记已解决）。"""
    did = update.get("id")
    if not did:
        return

    # 先获取行数据用于推送
    row = await fetch_one(db, "SELECT * FROM divergence_points WHERE id = ? AND discussion_id = ?",
                          (did, discussion_id))
    if row:
        # 标记为已解决后删除
        resolved_data = dict(row)
        resolved_data["resolved"] = True  # 前端可据此判断
        await sse_manager.broadcast(discussion_id, "divergence.update", resolved_data)

    await execute(
        db,
        "DELETE FROM divergence_points WHERE id = ? AND discussion_id = ?",
        (did, discussion_id),
    )
    logger.info(f"[讨论{discussion_id}] 分歧 #{did} 已消解并删除")


# ---- 查询接口 ----

async def list_consensus(discussion_id: int) -> dict:
    """查询共识列表（按更新时间倒序）。"""
    db = None
    try:
        from database import get_db
        db = await get_db()
        rows = await fetch_all(
            db,
            "SELECT * FROM consensus_points WHERE discussion_id = ? ORDER BY updated_at DESC",
            (discussion_id,),
        )
        return {"items": rows, "total": len(rows)}
    finally:
        if db:
            await db.close()


async def list_divergence(discussion_id: int) -> dict:
    """查询分歧列表（按更新时间倒序）。"""
    db = None
    try:
        from database import get_db
        db = await get_db()
        rows = await fetch_all(
            db,
            "SELECT * FROM divergence_points WHERE discussion_id = ? ORDER BY updated_at DESC",
            (discussion_id,),
        )
        return {"items": rows, "total": len(rows)}
    finally:
        if db:
            await db.close()
