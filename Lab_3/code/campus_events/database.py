"""SQLite 连接和数据库初始化。"""

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Iterator

from .event_models import EventError

SCHEMA_VERSION = 3


@contextmanager
def open_database(
    path: Path, *, create: bool = False
) -> Iterator[sqlite3.Connection]:
    """打开数据库，提交成功的写入或回滚失败的写入。"""
    mode = "rwc" if create else "rw"
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
    uri = f"{path.absolute().as_uri()}?mode={mode}"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            yield connection


def create_schema(connection: sqlite3.Connection) -> None:
    """创建数据库表，保留旧版本中的用户和活动。"""
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise EventError("数据库版本高于程序支持的版本，请使用更新的程序。")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            role TEXT NOT NULL CHECK (
                role IN ('participant', 'organizer', 'admin', 'checker')
            ),
            password_salt BLOB NOT NULL,
            password_hash BLOB NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY,
            organizer_id INTEGER NOT NULL REFERENCES users(id),
            name TEXT NOT NULL,
            kind TEXT NOT NULL,
            description TEXT NOT NULL,
            eligibility TEXT NOT NULL,
            status TEXT NOT NULL CHECK (
                status IN (
                    'draft', 'pending', 'rejected', 'published', 'cancelled'
                )
            ),
            review_note TEXT NOT NULL DEFAULT ''
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS event_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            starts_at TEXT NOT NULL,
            location TEXT NOT NULL,
            capacity INTEGER NOT NULL CHECK (capacity > 0),
            registration_deadline TEXT NOT NULL,
            UNIQUE (event_id, name)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS registration_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL
                REFERENCES event_sessions(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
            UNIQUE (session_id, name)
        )
        """
    )
    create_registration_schema(connection)
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def create_registration_schema(connection: sqlite3.Connection) -> None:
    """增加报名及资格数据，旧版活动与用户记录可直接复用。"""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS campus_memberships (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS category_session_identity
        ON registration_categories (id, session_id)
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            session_id INTEGER NOT NULL REFERENCES event_sessions(id),
            category_id INTEGER NOT NULL,
            participant_name TEXT NOT NULL,
            contact TEXT NOT NULL,
            received_at TEXT NOT NULL,
            status TEXT NOT NULL CHECK (
                status IN ('confirmed', 'waitlisted', 'cancelled')
            ),
            FOREIGN KEY (category_id, session_id)
                REFERENCES registration_categories (id, session_id)
        )
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS one_active_registration
        ON registrations (user_id, session_id)
        WHERE status IN ('confirmed', 'waitlisted')
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS registrations_by_session
        ON registrations (session_id, status, id)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS registrations_by_user
        ON registrations (user_id, id)
        """
    )


def require_current_schema(connection: sqlite3.Connection) -> None:
    """给使用旧数据库的用户提示升级命令。"""
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version < SCHEMA_VERSION:
        raise EventError("数据库需要升级，请先运行 init。")
    if version > SCHEMA_VERSION:
        raise EventError("数据库版本高于程序支持的版本，请使用更新的程序。")
