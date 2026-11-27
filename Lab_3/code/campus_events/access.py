"""用户、身份验证和角色权限。"""

import hashlib
import hmac
import sqlite3
from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    """用户在系统中担任的角色。"""

    PARTICIPANT = "participant"
    ORGANIZER = "organizer"
    ADMIN = "admin"
    CHECKER = "checker"


class Permission(str, Enum):
    """进入各业务功能所需的权限。"""

    BROWSE_EVENTS = "browse-events"
    MANAGE_EVENTS = "manage-events"
    REVIEW_EVENTS = "review-events"
    CHECK_IN = "check-in"
    REGISTRATIONS = "registrations"


PERMITTED_ROLES = {
    Permission.BROWSE_EVENTS: frozenset(Role),
    Permission.MANAGE_EVENTS: frozenset({Role.ORGANIZER}),
    Permission.REVIEW_EVENTS: frozenset({Role.ADMIN}),
    Permission.CHECK_IN: frozenset({Role.CHECKER}),
    Permission.REGISTRATIONS: frozenset({Role.PARTICIPANT}),
}


@dataclass(frozen=True, slots=True)
class User:
    """身份验证通过后的用户信息。"""

    id: int
    username: str
    name: str
    role: Role


class AuthenticationError(Exception):
    """用户名或密码未通过验证。"""


def hash_password(password: str, salt: bytes) -> bytes:
    """使用账号专属的盐值计算密码摘要。"""
    encoded = password.encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", encoded, salt, 600_000)


def authenticate(
    connection: sqlite3.Connection, username: str, password: str
) -> User:
    """检查数据库中的账号凭据，并读取该账号的角色。"""
    account = connection.execute(
        """
        SELECT id, username, name, role, password_salt, password_hash
        FROM users
        WHERE username = ?
        """,
        (username,),
    ).fetchone()
    # 两种失败都执行一次密码派生，也给出同一条错误提示。
    salt = account["password_salt"] if account is not None else bytes(16)
    candidate = hash_password(password, salt)
    if account is None or not hmac.compare_digest(
        candidate, account["password_hash"]
    ):
        raise AuthenticationError("用户名或密码不正确。")
    return User(
        id=account["id"],
        username=account["username"],
        name=account["name"],
        role=Role(account["role"]),
    )


def permissions_for(user: User) -> tuple[Permission, ...]:
    """列出当前用户可进入的业务功能。"""
    return tuple(
        permission
        for permission, roles in PERMITTED_ROLES.items()
        if user.role in roles
    )


def require_permission(user: User, permission: Permission) -> None:
    """拒绝角色不匹配的操作。"""
    if user.role not in PERMITTED_ROLES[permission]:
        raise PermissionError("当前账号没有权限进入此功能。")
