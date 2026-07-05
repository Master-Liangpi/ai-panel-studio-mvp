"""
AI Panel Studio — 嘉宾服务
"""

import logging
from database import get_db, fetch_one, fetch_all, execute
from services.llm import generate_panelists as llm_generate_panelists
from config import PANELIST_MIN_COUNT, PANELIST_MAX_COUNT

logger = logging.getLogger(__name__)


async def generate_panelists_for_discussion(
    discussion_id: int, count: int, topic_override: str | None = None
) -> dict:
    """
    调用 DeepSeek 生成嘉宾阵容并入库。

    Args:
        discussion_id: 讨论 ID
        count: 嘉宾人数
        topic_override: 覆盖话题

    Returns:
        {"host": {...}, "experts": [{...}], "items": [...]}

    Raises:
        ValueError: 参数不合法
        RuntimeError: AI 生成失败
    """
    # ---- 参数校验（对齐 TDD E1.1~E1.3） ----
    if count < PANELIST_MIN_COUNT or count > PANELIST_MAX_COUNT:
        raise ValueError(f"嘉宾人数必须在 {PANELIST_MIN_COUNT}~{PANELIST_MAX_COUNT} 之间，收到: {count}")

    db = await get_db()
    try:
        # 获取讨论信息
        discussion = await fetch_one(db, "SELECT * FROM discussions WHERE id = ?", (discussion_id,))
        if not discussion:
            raise ValueError(f"讨论 {discussion_id} 不存在")

        topic = topic_override or discussion["topic"] or discussion["title"]

        # ---- 调用 DeepSeek 生成 ----
        result = await llm_generate_panelists(topic, count)

        # ---- 入库 ----
        host_data = result["host"]
        host_id = await execute(
            db,
            """INSERT INTO panelists (discussion_id, name, title, stance, color, role)
               VALUES (?, ?, ?, ?, ?, 'host')""",
            (discussion_id, host_data["name"], host_data.get("title", ""),
             host_data["stance"], host_data["color"]),
        )
        host = await fetch_one(db, "SELECT * FROM panelists WHERE id = ?", (host_id,))
        host = dict(host) if host else None

        experts = []
        for expert_data in result["experts"]:
            eid = await execute(
                db,
                """INSERT INTO panelists (discussion_id, name, title, stance, color, role)
                   VALUES (?, ?, ?, ?, ?, 'expert')""",
                (discussion_id, expert_data["name"], expert_data.get("title", ""),
                 expert_data["stance"], expert_data["color"]),
            )
            erow = await fetch_one(db, "SELECT * FROM panelists WHERE id = ?", (eid,))
            if erow:
                experts.append(dict(erow))

        # 更新讨论时间戳
        await execute(
            db,
            "UPDATE discussions SET updated_at = datetime('now', 'localtime') WHERE id = ?",
            (discussion_id,),
        )

        all_items = ([host] if host else []) + experts
        return {"host": host, "experts": experts, "items": all_items}

    finally:
        await db.close()


async def list_panelists(discussion_id: int) -> dict:
    """查询讨论的嘉宾列表。"""
    db = await get_db()
    try:
        rows = await fetch_all(
            db,
            "SELECT * FROM panelists WHERE discussion_id = ? ORDER BY role DESC, id ASC",
            (discussion_id,),
        )
        host = next((r for r in rows if r["role"] == "host"), None)
        experts = [r for r in rows if r["role"] == "expert"]
        return {"items": rows, "host": host, "experts": experts}
    finally:
        await db.close()


async def add_panelist(discussion_id: int, **kwargs) -> dict:
    """手动添加嘉宾。"""
    db = await get_db()
    try:
        # 校验：已有主持人时不允许再添加 host
        if kwargs.get("role") == "host":
            existing = await fetch_one(
                db,
                "SELECT id FROM panelists WHERE discussion_id = ? AND role = 'host'",
                (discussion_id,),
            )
            if existing:
                raise ValueError("每场讨论只能有一位主持人")

        pid = await execute(
            db,
            """INSERT INTO panelists (discussion_id, name, title, stance, color, role, avatar_url)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (discussion_id, kwargs["name"], kwargs.get("title", ""),
             kwargs.get("stance", ""), kwargs.get("color", "#3388FF"),
             kwargs["role"], kwargs.get("avatar_url")),
        )
        row = await fetch_one(db, "SELECT * FROM panelists WHERE id = ?", (pid,))
        await execute(
            db,
            "UPDATE discussions SET updated_at = datetime('now', 'localtime') WHERE id = ?",
            (discussion_id,),
        )
        return dict(row) if row else {}
    finally:
        await db.close()


async def update_panelist(discussion_id: int, panelist_id: int, **kwargs) -> dict | None:
    """更新嘉宾信息。"""
    allowed = {"name", "title", "stance", "color", "role", "avatar_url"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        rows = await list_panelists(discussion_id)
        for p in rows["items"]:
            if p["id"] == panelist_id:
                return p
        return None

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [discussion_id, panelist_id]

    db = await get_db()
    try:
        await execute(
            db,
            f"UPDATE panelists SET {set_clause} WHERE discussion_id = ? AND id = ?",
            tuple(params),
        )
        row = await fetch_one(db, "SELECT * FROM panelists WHERE id = ?", (panelist_id,))
        return dict(row) if row else None
    finally:
        await db.close()


async def delete_panelist(discussion_id: int, panelist_id: int) -> bool:
    """删除嘉宾。历史发言保留（panelist_id 在 speeches 表有 ON DELETE CASCADE？不——我们保留发言）。"""
    db = await get_db()
    try:
        # 先置空该嘉宾的 speeches 引用（保留发言内容）
        await execute(
            db,
            "UPDATE speeches SET panelist_id = NULL WHERE panelist_id = ? AND discussion_id = ?",
            (panelist_id, discussion_id),
        )
        cursor = await db.execute(
            "DELETE FROM panelists WHERE discussion_id = ? AND id = ?",
            (discussion_id, panelist_id),
        )
        await db.commit()
        deleted = cursor.rowcount > 0
        await cursor.close()
        return deleted
    finally:
        await db.close()
