"""
AI Panel Studio — 讨论会话服务
"""

import logging
from database import get_db, fetch_one, fetch_all, execute

logger = logging.getLogger(__name__)


async def create_discussion(title: str, topic: str = "") -> dict:
    """新建讨论会话。"""
    db = await get_db()
    try:
        disc_id = await execute(
            db,
            "INSERT INTO discussions (title, topic) VALUES (?, ?)",
            (title, topic),
        )
        return await get_discussion(db, disc_id)
    finally:
        await db.close()


async def get_discussion(db_or_id, discussion_id: int | None = None) -> dict | None:
    """
    查询单场讨论详情。
    支持传入 db 连接复用或 discussion_id 独立查询。
    """
    if isinstance(db_or_id, int) or (discussion_id is None and isinstance(db_or_id, int)):
        # 传入的是 discussion_id
        did = db_or_id if isinstance(db_or_id, int) else discussion_id
        db = await get_db()
        try:
            return await _get_discussion_impl(db, did)
        finally:
            await db.close()
    else:
        # 传入的是 db 连接
        return await _get_discussion_impl(db_or_id, discussion_id)


async def _get_discussion_impl(db, discussion_id: int) -> dict | None:
    """内部实现。"""
    row = await fetch_one(
        db,
        """SELECT d.*,
                  (SELECT COUNT(*) FROM panelists WHERE discussion_id = d.id) AS panelist_count,
                  (SELECT COUNT(*) FROM speeches WHERE discussion_id = d.id) AS speech_count
           FROM discussions d WHERE d.id = ?""",
        (discussion_id,),
    )
    return row


async def list_discussions(status: str | None = None, page: int = 1, page_size: int = 20) -> dict:
    """分页查询讨论列表，按更新时间倒序。"""
    db = await get_db()
    try:
        where_clause = ""
        params: list = []
        if status and status in ("active", "paused", "completed"):
            where_clause = "WHERE d.status = ?"
            params.append(status)

        # 总数
        count_row = await fetch_one(
            db,
            f"SELECT COUNT(*) AS total FROM discussions d {where_clause}",
            tuple(params),
        )
        total = count_row["total"] if count_row else 0

        # 分页数据
        offset = (page - 1) * page_size
        rows = await fetch_all(
            db,
            f"""SELECT d.*,
                       (SELECT COUNT(*) FROM panelists WHERE discussion_id = d.id) AS panelist_count,
                       (SELECT COUNT(*) FROM speeches WHERE discussion_id = d.id) AS speech_count
                FROM discussions d {where_clause}
                ORDER BY d.updated_at DESC
                LIMIT ? OFFSET ?""",
            tuple(params + [page_size, offset]),
        )
        return {"items": rows, "total": total}
    finally:
        await db.close()


async def update_discussion(discussion_id: int, **kwargs) -> dict | None:
    """更新讨论信息。"""
    allowed = {"title", "topic", "status"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return await get_discussion(discussion_id)

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    set_clause += ", updated_at = datetime('now', 'localtime')"
    params = list(updates.values()) + [discussion_id]

    db = await get_db()
    try:
        await execute(db, f"UPDATE discussions SET {set_clause} WHERE id = ?", tuple(params))
        return await _get_discussion_impl(db, discussion_id)
    finally:
        await db.close()


async def delete_discussion(discussion_id: int) -> bool:
    """删除讨论（级联删除子表数据）。"""
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM discussions WHERE id = ?", (discussion_id,))
        await db.commit()
        deleted = cursor.rowcount > 0
        await cursor.close()
        return deleted
    finally:
        await db.close()


async def discussion_exists(discussion_id: int) -> bool:
    """检查讨论是否存在。"""
    db = await get_db()
    try:
        row = await fetch_one(db, "SELECT 1 FROM discussions WHERE id = ?", (discussion_id,))
        return row is not None
    finally:
        await db.close()
