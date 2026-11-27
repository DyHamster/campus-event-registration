"""本地演示数据。"""

import secrets
import sqlite3
from hmac import compare_digest

from .access import Role, hash_password

DEMO_PASSWORD = "campus-demo"
DEMO_ACCOUNTS = (
    ("student", "演示参与者", Role.PARTICIPANT, True),
    ("student2", "演示参与者乙", Role.PARTICIPANT, True),
    ("student3", "演示参与者丙", Role.PARTICIPANT, True),
    ("visitor", "校外演示参与者", Role.PARTICIPANT, False),
    ("organizer", "演示举办方", Role.ORGANIZER, False),
    ("admin", "演示管理员", Role.ADMIN, False),
    ("checker", "演示检票员", Role.CHECKER, False),
)


def seed_demo_accounts(connection: sqlite3.Connection) -> int:
    """添加缺失的演示用户，返回新建账号数量。"""
    added = 0
    for username, name, role, is_member in DEMO_ACCOUNTS:
        existing = connection.execute(
            """
            SELECT users.*, campus_memberships.user_id AS membership
            FROM users
            LEFT JOIN campus_memberships
                ON campus_memberships.user_id = users.id
            WHERE username = ?
            """,
            (username,),
        ).fetchone()
        if existing is not None:
            if is_member:
                _restore_demo_membership(connection, existing, name, role)
            continue
        salt = secrets.token_bytes(16)
        digest = hash_password(DEMO_PASSWORD, salt)
        cursor = connection.execute(
            """
            INSERT INTO users (
                username, name, role, password_salt, password_hash
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, name, role.value, salt, digest),
        )
        if is_member:
            _add_membership(connection, cursor.lastrowid)
        added += 1
    return added


def _restore_demo_membership(
    connection: sqlite3.Connection, account: sqlite3.Row, name: str, role: Role
) -> None:
    """升级旧演示库时，只标记仍匹配演示凭据的账号。"""
    if account["membership"] is not None:
        return
    if account["name"] != name or account["role"] != role.value:
        return
    actual = hash_password(DEMO_PASSWORD, account["password_salt"])
    if compare_digest(actual, account["password_hash"]):
        _add_membership(connection, account["id"])


def _add_membership(connection: sqlite3.Connection, user_id: int) -> None:
    connection.execute(
        "INSERT INTO campus_memberships (user_id) VALUES (?)", (user_id,)
    )
