"""本地演示数据。"""

import secrets
import sqlite3

from .access import Role, hash_password

DEMO_PASSWORD = "campus-demo"
DEMO_ACCOUNTS = (
    ("student", "演示参与者", Role.PARTICIPANT),
    ("organizer", "演示举办方", Role.ORGANIZER),
    ("admin", "演示管理员", Role.ADMIN),
    ("checker", "演示检票员", Role.CHECKER),
)


def seed_demo_accounts(connection: sqlite3.Connection) -> int:
    """添加缺失的演示用户，返回新建账号数量。"""
    added = 0
    for username, name, role in DEMO_ACCOUNTS:
        existing = connection.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing is not None:
            continue
        salt = secrets.token_bytes(16)
        digest = hash_password(DEMO_PASSWORD, salt)
        connection.execute(
            """
            INSERT INTO users (
                username, name, role, password_salt, password_hash
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, name, role.value, salt, digest),
        )
        added += 1
    return added
