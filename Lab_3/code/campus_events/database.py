"""SQLite 连接和数据库初始化。"""

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Iterator


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
    """创建第一阶段所需的用户表，可在已有数据库上重复执行。"""
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
