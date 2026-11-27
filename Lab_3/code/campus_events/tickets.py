"""电子票的发放、作废与本人查询。"""

import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from .access import Permission, User, require_permission


class TicketError(Exception):
    """电子票、检票或二维码命令无法完成。"""


class TicketStatus(str, Enum):
    """根据票据和签到记录得到的票据状态。"""

    VALID = "valid"
    CHECKED_IN = "checked_in"
    VOID = "void"


@dataclass(frozen=True, slots=True)
class Ticket:
    """参与者本人可查阅的电子票。"""

    registration_id: int
    event_name: str
    session_id: int
    session_name: str
    starts_at: datetime
    location: str
    code: str
    checked_at: datetime | None
    voided_at: datetime | None

    @property
    def status(self) -> TicketStatus:
        if self.voided_at is not None:
            return TicketStatus.VOID
        if self.checked_at is not None:
            return TicketStatus.CHECKED_IN
        return TicketStatus.VALID


def utc_now() -> datetime:
    """票据和签到记录使用的服务器时间。"""
    return datetime.now(timezone.utc)


def issue_ticket(
    connection: sqlite3.Connection, registration_id: int, issued_at: datetime
) -> None:
    """在报名事务中为记录分配一张唯一的票。"""
    code = f"CE1-{secrets.token_urlsafe(24)}"
    connection.execute(
        """
        INSERT INTO tickets (registration_id, code, issued_at)
        VALUES (?, ?, ?)
        ON CONFLICT (registration_id) DO NOTHING
        """,
        (registration_id, code, issued_at.isoformat()),
    )


def backfill_tickets(connection: sqlite3.Connection) -> None:
    """给升级前仍有效的已确认报名补发电子票。"""
    rows = connection.execute(
        """
        SELECT registration.id
        FROM registrations AS registration
        JOIN event_sessions AS session ON session.id = registration.session_id
        JOIN events AS event ON event.id = session.event_id
        WHERE registration.status = 'confirmed' AND event.status = 'published'
        """
    )
    issued_at = utc_now()
    for row in rows:
        issue_ticket(connection, row["id"], issued_at)


def void_ticket(
    connection: sqlite3.Connection, registration_id: int, voided_at: datetime
) -> None:
    """作废一条报名的票据，保留原票码和历史。"""
    connection.execute(
        """
        UPDATE tickets SET voided_at = ?
        WHERE registration_id = ? AND voided_at IS NULL
        """,
        (voided_at.isoformat(), registration_id),
    )


def void_event_tickets(connection: sqlite3.Connection, event_id: int) -> None:
    """活动取消时作废所有所属场次的电子票。"""
    connection.execute(
        """
        UPDATE tickets SET voided_at = ?
        WHERE voided_at IS NULL
          AND registration_id IN (
              SELECT registration.id
              FROM registrations AS registration
              JOIN event_sessions AS session
                  ON session.id = registration.session_id
              WHERE session.event_id = ?
          )
        """,
        (utc_now().isoformat(), event_id),
    )


def owned_ticket(
    connection: sqlite3.Connection, user: User, registration_id: int
) -> Ticket:
    """按参与者身份查询本人票据，保留作废状态供查询。"""
    require_permission(user, Permission.REGISTRATIONS)
    row = connection.execute(
        """
        SELECT ticket.code, ticket.voided_at, check_in.checked_at,
               event.name AS event_name, session.name AS session_name,
               session.id AS session_id, session.starts_at, session.location
        FROM registrations AS registration
        JOIN event_sessions AS session ON session.id = registration.session_id
        JOIN events AS event ON event.id = session.event_id
        LEFT JOIN tickets AS ticket ON ticket.registration_id = registration.id
        LEFT JOIN check_ins AS check_in ON check_in.ticket_id = ticket.id
        WHERE registration.id = ? AND registration.user_id = ?
        """,
        (registration_id, user.id),
    ).fetchone()
    if row is None:
        raise TicketError(f"找不到本人报名记录 #{registration_id}。")
    if row["code"] is None:
        raise TicketError("该报名记录暂无电子票。")
    return Ticket(
        registration_id=registration_id,
        event_name=row["event_name"],
        session_id=row["session_id"],
        session_name=row["session_name"],
        starts_at=datetime.fromisoformat(row["starts_at"]),
        location=row["location"],
        code=row["code"],
        checked_at=parse_optional_time(row["checked_at"]),
        voided_at=parse_optional_time(row["voided_at"]),
    )


def parse_optional_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value is not None else None
