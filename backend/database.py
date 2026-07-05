"""
AI Panel Studio — 数据库层
SQLite + WAL 模式，支持多读者并发。
"""

import os
import aiosqlite
from pathlib import Path
from config import DATABASE_PATH


async def get_db() -> aiosqlite.Connection:
    """
    获取数据库连接。
    每次调用创建新连接（aiosqlite 连接池轻量，无严重性能开销）。
    WAL 模式下读写互不阻塞。
    """
    db_dir = Path(DATABASE_PATH).parent
    os.makedirs(db_dir, exist_ok=True)

    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_database() -> None:
    """
    应用启动时初始化数据库：
    1. 创建 data 目录
    2. 执行 init_db.sql 建表
    """
    db_dir = Path(DATABASE_PATH).parent
    os.makedirs(db_dir, exist_ok=True)

    sql_path = Path(__file__).parent / "init_db.sql"
    if not sql_path.exists():
        raise FileNotFoundError(f"找不到 init_db.sql: {sql_path}")

    sql_content = sql_path.read_text(encoding="utf-8")

    db = await get_db()
    try:
        await db.executescript(sql_content)
        await db.commit()
    finally:
        await db.close()


async def fetch_one(db: aiosqlite.Connection, sql: str, params: tuple = ()) -> dict | None:
    """执行查询，返回单行 dict 或 None。"""
    cursor = await db.execute(sql, params)
    row = await cursor.fetchone()
    await cursor.close()
    if row is None:
        return None
    return dict(row)


async def fetch_all(db: aiosqlite.Connection, sql: str, params: tuple = ()) -> list[dict]:
    """执行查询，返回多行 dict 列表。"""
    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()
    await cursor.close()
    return [dict(row) for row in rows]


async def execute(db: aiosqlite.Connection, sql: str, params: tuple = ()) -> int:
    """执行写操作，返回 lastrowid。"""
    cursor = await db.execute(sql, params)
    await db.commit()
    last_id = cursor.lastrowid
    await cursor.close()
    return last_id


async def execute_many(db: aiosqlite.Connection, sql: str, params_list: list[tuple]) -> None:
    """批量执行写操作。"""
    await db.executemany(sql, params_list)
    await db.commit()
