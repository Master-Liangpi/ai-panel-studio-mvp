-- ============================================================
-- AI Panel Studio — SQLite 数据库初始化脚本
-- 执行方式: sqlite3 data/ai_panel_studio.db < init_db.sql
-- 或在 Python 中调用 database.init_database()
-- ============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------
-- 1. 讨论会话表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS discussions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    topic       TEXT    NOT NULL DEFAULT '',
    status      TEXT    NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'paused', 'completed')),
    created_at  DATETIME NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at  DATETIME NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ----------------------------------------------------------
-- 2. 嘉宾表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS panelists (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discussion_id   INTEGER NOT NULL,
    name            TEXT    NOT NULL,
    title           TEXT    NOT NULL DEFAULT '',
    stance          TEXT    NOT NULL DEFAULT '',
    color           TEXT    NOT NULL DEFAULT '#3388FF',
    role            TEXT    NOT NULL CHECK (role IN ('host', 'expert')),
    avatar_url      TEXT,
    created_at      DATETIME NOT NULL DEFAULT (datetime('now', 'localtime')),

    FOREIGN KEY (discussion_id)
        REFERENCES discussions (id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_panelists_discussion_id
    ON panelists (discussion_id);

-- ----------------------------------------------------------
-- 3. 发言表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS speeches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discussion_id   INTEGER NOT NULL,
    panelist_id     INTEGER NOT NULL,
    content         TEXT    NOT NULL,
    sequence_num    INTEGER NOT NULL,
    created_at      DATETIME NOT NULL DEFAULT (datetime('now', 'localtime')),

    FOREIGN KEY (discussion_id)
        REFERENCES discussions (id)
        ON DELETE CASCADE,

    FOREIGN KEY (panelist_id)
        REFERENCES panelists (id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_speeches_discussion_id
    ON speeches (discussion_id);

CREATE INDEX IF NOT EXISTS idx_speeches_panelist_id
    ON speeches (panelist_id);

CREATE INDEX IF NOT EXISTS idx_speeches_discussion_seq
    ON speeches (discussion_id, sequence_num);

-- ----------------------------------------------------------
-- 4. 共识表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS consensus_points (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    discussion_id     INTEGER  NOT NULL,
    topic             TEXT     NOT NULL,
    content           TEXT     NOT NULL DEFAULT '',
    latest_speech_id  INTEGER,
    created_at        DATETIME NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at        DATETIME NOT NULL DEFAULT (datetime('now', 'localtime')),

    FOREIGN KEY (discussion_id)
        REFERENCES discussions (id)
        ON DELETE CASCADE,

    FOREIGN KEY (latest_speech_id)
        REFERENCES speeches (id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_consensus_discussion_id
    ON consensus_points (discussion_id);

CREATE INDEX IF NOT EXISTS idx_consensus_discussion_updated
    ON consensus_points (discussion_id, updated_at);

-- ----------------------------------------------------------
-- 5. 分歧表
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS divergence_points (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    discussion_id     INTEGER  NOT NULL,
    topic             TEXT     NOT NULL,
    content           TEXT     NOT NULL DEFAULT '',
    sides             TEXT     NOT NULL DEFAULT '',
    latest_speech_id  INTEGER,
    created_at        DATETIME NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at        DATETIME NOT NULL DEFAULT (datetime('now', 'localtime')),

    FOREIGN KEY (discussion_id)
        REFERENCES discussions (id)
        ON DELETE CASCADE,

    FOREIGN KEY (latest_speech_id)
        REFERENCES speeches (id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_divergence_discussion_id
    ON divergence_points (discussion_id);

CREATE INDEX IF NOT EXISTS idx_divergence_discussion_updated
    ON divergence_points (discussion_id, updated_at);
