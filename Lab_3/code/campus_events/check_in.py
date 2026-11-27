"""按场次授权检票和核验电子票。"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from .access import Permission, Role, User, require_permission
from .audit import AuditAction, AuditOutcome, record_audit
from .event_models import EventStatus
from .tickets import TicketError, utc_now


@dataclass(frozen=True, slots=True)
class CheckerAssignment:
    """检票员被授权的场次。"""

    checker_username: str
    session_id: int
    event_name: str
    session_name: str
    location: str


@dataclass(frozen=True, slots=True)
class CheckInResult:
    """检票结果，重复检票时返回首次签到时间。"""

    session_id: int
    registration_id: int
    participant_name: str
    checked_at: datetime
    duplicate: bool


ASSIGNMENTS_QUERY = """
    SELECT checker.username, session.id AS session_id, session.location,
           event.name AS event_name, session.name AS session_name
    FROM session_checkers AS assignment
    JOIN users AS checker ON checker.id = assignment.checker_id
    JOIN event_sessions AS session ON session.id = assignment.session_id
    JOIN events AS event ON event.id = session.event_id
"""


class CheckInService:
    """管理场次授权或在授权范围内记录签到。"""

    def __init__(self, connection: sqlite3.Connection, user: User) -> None:
        self.connection = connection
        self.user = user

    def grant(self, session_id: int, checker_username: str) -> None:
        """由管理员授权一位检票员核验已发布活动的指定场次。"""
        require_permission(self.user, Permission.CHECKER_ACCESS)
        self.connection.execute("BEGIN IMMEDIATE")
        checker_id = self._checker_id(checker_username)
        session = self.connection.execute(
            """
            SELECT event.status
            FROM event_sessions AS session
            JOIN events AS event ON event.id = session.event_id
            WHERE session.id = ?
            """,
            (session_id,),
        ).fetchone()
        if session is None or session["status"] != EventStatus.PUBLISHED.value:
            raise TicketError("只能为已发布活动的场次授予检票权限。")

        self.connection.execute(
            """
            INSERT INTO session_checkers (checker_id, session_id) VALUES (?, ?)
            ON CONFLICT (checker_id, session_id) DO NOTHING
            """,
            (checker_id, session_id),
        )
        record_audit(
            self.connection, self.user, AuditAction.CHECKER_GRANT, session_id
        )

    def revoke(self, session_id: int, checker_username: str) -> None:
        """撤销指定场次的检票授权。"""
        require_permission(self.user, Permission.CHECKER_ACCESS)
        self.connection.execute("BEGIN IMMEDIATE")
        checker_id = self._checker_id(checker_username)
        self.connection.execute(
            """
            DELETE FROM session_checkers
            WHERE checker_id = ? AND session_id = ?
            """,
            (checker_id, session_id),
        )
        record_audit(
            self.connection, self.user, AuditAction.CHECKER_REVOKE, session_id
        )

    def list_assignments(self) -> tuple[CheckerAssignment, ...]:
        """管理员查看已分配的检票权限。"""
        require_permission(self.user, Permission.CHECKER_ACCESS)
        rows = self.connection.execute(
            ASSIGNMENTS_QUERY + " ORDER BY session.id, checker.username"
        )
        return tuple(_assignment(row) for row in rows)

    def own_sessions(self) -> tuple[CheckerAssignment, ...]:
        """检票员查看本人获授权且活动仍在发布状态的场次。"""
        require_permission(self.user, Permission.CHECK_IN)
        rows = self.connection.execute(
            ASSIGNMENTS_QUERY
            + """
            WHERE assignment.checker_id = ? AND event.status = ?
            ORDER BY session.id
            """,
            (self.user.id, EventStatus.PUBLISHED.value),
        )
        return tuple(_assignment(row) for row in rows)

    def verify(self, session_id: int, code: str) -> CheckInResult:
        """核验场次、票据和授权，在一个事务中记录首次签到。"""
        require_permission(self.user, Permission.CHECK_IN)
        self.connection.execute("BEGIN IMMEDIATE")
        if not self._has_access(session_id):
            raise PermissionError("当前检票员未获该场次的检票授权。")

        ticket = self.connection.execute(
            """
            SELECT ticket.id, ticket.voided_at, registration.session_id,
                   registration.id AS registration_id,
                   registration.participant_name, registration.status,
                   event.status AS event_status, check_in.checked_at
            FROM tickets AS ticket
            JOIN registrations AS registration
                ON registration.id = ticket.registration_id
            JOIN event_sessions AS session
                ON session.id = registration.session_id
            JOIN events AS event ON event.id = session.event_id
            LEFT JOIN check_ins AS check_in ON check_in.ticket_id = ticket.id
            WHERE ticket.code = ?
            """,
            (code.strip(),),
        ).fetchone()
        if ticket is None:
            raise TicketError("票码无效。")
        if ticket["session_id"] != session_id:
            raise TicketError("电子票不属于当前场次。")
        if (
            ticket["voided_at"] is not None
            or ticket["event_status"] != EventStatus.PUBLISHED.value
            or ticket["status"] != "confirmed"
        ):
            raise TicketError("电子票已失效。")

        duplicate = ticket["checked_at"] is not None
        if duplicate:
            checked_at = datetime.fromisoformat(ticket["checked_at"])
        else:
            checked_at = utc_now()
            self.connection.execute(
                """
                INSERT INTO check_ins (ticket_id, checker_id, checked_at)
                VALUES (?, ?, ?)
                """,
                (ticket["id"], self.user.id, checked_at.isoformat()),
            )
        outcome = AuditOutcome.DUPLICATE if duplicate else AuditOutcome.SUCCESS
        record_audit(
            self.connection, self.user, AuditAction.CHECK_IN, session_id,
            outcome=outcome,
        )
        return CheckInResult(
            session_id=session_id,
            registration_id=ticket["registration_id"],
            participant_name=ticket["participant_name"],
            checked_at=checked_at,
            duplicate=duplicate,
        )

    def _checker_id(self, username: str) -> int:
        checker = self.connection.execute(
            "SELECT id FROM users WHERE username = ? AND role = ?",
            (username, Role.CHECKER.value),
        ).fetchone()
        if checker is None:
            raise TicketError("找不到该检票员账号。")
        return checker["id"]

    def _has_access(self, session_id: int) -> bool:
        assignment = self.connection.execute(
            """
            SELECT 1 FROM session_checkers
            WHERE checker_id = ? AND session_id = ?
            """,
            (self.user.id, session_id),
        ).fetchone()
        return assignment is not None


def _assignment(row: sqlite3.Row) -> CheckerAssignment:
    return CheckerAssignment(
        checker_username=row["username"],
        session_id=row["session_id"],
        event_name=row["event_name"],
        session_name=row["session_name"],
        location=row["location"],
    )
