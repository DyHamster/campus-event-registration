"""记录并查询关键业务操作。"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from .access import Permission, User, require_permission


class AuditAction(str, Enum):
    """可筛选的操作类型。"""

    EVENT_CREATE = "event.create"
    EVENT_EDIT = "event.edit"
    EVENT_SUBMIT = "event.submit"
    EVENT_APPROVE = "event.approve"
    EVENT_REJECT = "event.reject"
    EVENT_CANCEL = "event.cancel"
    CHECKER_GRANT = "checker.grant"
    CHECKER_REVOKE = "checker.revoke"
    CHECK_IN = "ticket.check-in"
    ROSTER_EXPORT = "roster.export"


class AuditOutcome(str, Enum):
    """关键操作的执行结果。"""

    SUCCESS = "success"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """管理员可查看的操作及其目标。"""

    id: int
    actor: str
    action: AuditAction
    target_id: int | None
    outcome: AuditOutcome
    occurred_at: datetime


def record_audit(
    connection: sqlite3.Connection,
    actor: User,
    action: AuditAction,
    target_id: int | None,
    *,
    outcome: AuditOutcome = AuditOutcome.SUCCESS,
) -> None:
    """在调用方事务内追加日志，日志中只保存操作和目标编号。"""
    connection.execute(
        """
        INSERT INTO audit_logs (
            actor_id, action, target_id, outcome, occurred_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            actor.id, action.value, target_id, outcome.value,
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def recent_entries(
    connection: sqlite3.Connection,
    user: User,
    *,
    action: AuditAction | None = None,
    outcome: AuditOutcome | None = None,
    limit: int = 50,
) -> tuple[AuditEntry, ...]:
    """管理员按操作或结果查看最近的记录。"""
    require_permission(user, Permission.AUDIT)
    action_value = action.value if action is not None else None
    outcome_value = outcome.value if outcome is not None else None
    rows = connection.execute(
        """
        SELECT entry.*, users.username
        FROM audit_logs AS entry
        JOIN users ON users.id = entry.actor_id
        WHERE (? IS NULL OR entry.action = ?)
          AND (? IS NULL OR entry.outcome = ?)
        ORDER BY entry.id DESC
        LIMIT ?
        """,
        (action_value, action_value, outcome_value, outcome_value, limit),
    )
    return tuple(
        AuditEntry(
            id=row["id"],
            actor=row["username"],
            action=AuditAction(row["action"]),
            target_id=row["target_id"],
            outcome=AuditOutcome(row["outcome"]),
            occurred_at=datetime.fromisoformat(row["occurred_at"]),
        )
        for row in rows
    )
