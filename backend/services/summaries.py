"""
AI Panel Studio — 总结服务
"""

import logging
from datetime import datetime

from database import get_db, fetch_one, fetch_all, execute
from services.llm import generate_summary as llm_generate_summary

logger = logging.getLogger(__name__)

# 总结缓存（内存缓存，key=discussion_id，服务重启后需重新生成）
_summary_cache: dict[int, dict] = {}


async def get_summary(discussion_id: int) -> dict | None:
    """获取已缓存的总结（内存缓存，不存在则返回 None 提示需生成）。"""
    return _summary_cache.get(discussion_id)


async def generate_summary_for_discussion(discussion_id: int) -> dict:
    """
    调用 DeepSeek 生成收尾总结。

    1. 获取全量上下文（发言、共识、分歧、嘉宾）
    2. 调用 LLM 生成 Markdown 总结
    3. 更新讨论状态为 completed
    4. 缓存总结

    Raises:
        ValueError: 无发言数据或讨论不存在
    """
    db = await get_db()
    try:
        discussion = await fetch_one(db, "SELECT * FROM discussions WHERE id = ?", (discussion_id,))
        if not discussion:
            raise ValueError("讨论不存在")

        # 获取全量数据
        speeches = await fetch_all(
            db,
            """SELECT s.*, COALESCE(p.name, '(离场)') AS panelist_name,
                       COALESCE(p.role, 'expert') AS panelist_role
               FROM speeches s LEFT JOIN panelists p ON s.panelist_id = p.id
               WHERE s.discussion_id = ? ORDER BY s.sequence_num ASC""",
            (discussion_id,),
        )
        if not speeches:
            raise ValueError("该讨论尚无任何发言，无法生成总结")

        consensus = await fetch_all(
            db,
            "SELECT * FROM consensus_points WHERE discussion_id = ? ORDER BY updated_at DESC",
            (discussion_id,),
        )
        divergence = await fetch_all(
            db,
            "SELECT * FROM divergence_points WHERE discussion_id = ? ORDER BY updated_at DESC",
            (discussion_id,),
        )
        panelists = await fetch_all(
            db,
            "SELECT * FROM panelists WHERE discussion_id = ?",
            (discussion_id,),
        )

        # 调用 LLM 生成
        summary_content = await llm_generate_summary(
            discussion_topic=discussion["topic"] or discussion["title"],
            all_speeches=speeches,
            consensus_points=consensus,
            divergence_points=divergence,
            panelists=panelists,
        )

        # 标记讨论完成
        await execute(
            db,
            "UPDATE discussions SET status = 'completed', updated_at = datetime('now', 'localtime') WHERE id = ?",
            (discussion_id,),
        )

        generated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        summary_obj = {
            "discussion_id": discussion_id,
            "content": summary_content,
            "generated_at": generated_at,
        }

        # 缓存（覆盖旧值）
        _summary_cache[discussion_id] = summary_obj

        return summary_obj

    finally:
        await db.close()
