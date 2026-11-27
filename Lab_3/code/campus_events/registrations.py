"""报名、候补与递补，按场次分配名额。"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from .access import Permission, User, require_permission
from .event_models import EventStatus
from .tickets import (
    Ticket,
    issue_ticket,
    owned_ticket,
    parse_optional_time,
    void_ticket,
)


class RegistrationError(Exception):
    """报名资料无效，或当前状态不允许这项操作。"""


class RegistrationStatus(str, Enum):
    """一条报名记录的状态。"""

    CONFIRMED = "confirmed"
    WAITLISTED = "waitlisted"
    CANCELLED = "cancelled"


STATUS_NAMES = {
    RegistrationStatus.CONFIRMED: "报名成功",
    RegistrationStatus.WAITLISTED: "候补中",
    RegistrationStatus.CANCELLED: "已取消",
}


@dataclass(frozen=True, slots=True)
class Registration:
    """参与者可查看的本人报名记录。"""

    id: int
    session_id: int
    category_id: int
    event_name: str
    session_name: str
    category_name: str
    participant_name: str
    contact: str
    received_at: datetime
    status: RegistrationStatus
    waitlist_position: int | None
    checked_at: datetime | None


@dataclass(frozen=True, slots=True)
class ApplicationResult:
    """报名操作返回记录及是否复用已有记录。"""

    registration: Registration
    existing: bool


REGISTRATION_QUERY = """
    SELECT record.*, event.name AS event_name, session.name AS session_name,
           category.name AS category_name, check_in.checked_at,
           CASE WHEN record.status = 'waitlisted' THEN 1 + (
               SELECT COUNT(*) FROM registrations AS earlier
               WHERE earlier.session_id = record.session_id
                 AND earlier.status = 'waitlisted'
                 AND earlier.id < record.id
           ) END AS waitlist_position
    FROM registrations AS record
    JOIN event_sessions AS session ON session.id = record.session_id
    JOIN events AS event ON event.id = session.event_id
    JOIN registration_categories AS category
        ON category.id = record.category_id
    LEFT JOIN tickets AS ticket ON ticket.registration_id = record.id
    LEFT JOIN check_ins AS check_in ON check_in.ticket_id = ticket.id
"""


class RegistrationService:
    """使用当前参与者身份操作，事务由调用者提交或回滚。"""

    def __init__(self, connection: sqlite3.Connection, user: User) -> None:
        self.connection = connection
        self.user = user

    def apply(
        self,
        session_id: int,
        category_id: int,
        *,
        name: str,
        contact: str,
        join_waitlist: bool,
    ) -> ApplicationResult:
        """分配名额或加入候补。取得写事务时记录系统接收时间。"""
        require_permission(self.user, Permission.REGISTRATIONS)
        self.connection.execute("BEGIN IMMEDIATE")
        received_at = utc_now()
        existing = self._active_registration_id(session_id)
        if existing is not None:
            return ApplicationResult(self._get_owned(existing), existing=True)

        session = self._get_session(session_id)
        if session["event_status"] != EventStatus.PUBLISHED.value:
            raise RegistrationError("活动当前未开放报名。")
        deadline = datetime.fromisoformat(session["registration_deadline"])
        if received_at >= deadline:
            raise RegistrationError("该场次报名已截止。")
        campus_only = _campus_only(session["eligibility"])
        if campus_only and not self._is_campus_member():
            raise RegistrationError("该活动仅接受校内师生报名。")

        self._require_category(session_id, category_id)
        name, contact = name.strip(), contact.strip()
        if not name or not contact:
            raise RegistrationError("请填写姓名和联系方式。")

        if self._confirmed_count(session_id) < session["capacity"]:
            status = RegistrationStatus.CONFIRMED
        elif join_waitlist:
            status = RegistrationStatus.WAITLISTED
        else:
            raise RegistrationError("场次名额已满，可以选择加入候补。")

        cursor = self.connection.execute(
            """
            INSERT INTO registrations (
                user_id, session_id, category_id, participant_name, contact,
                received_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.user.id, session_id, category_id, name, contact,
                received_at.isoformat(), status.value,
            ),
        )
        registration_id = cursor.lastrowid
        if status is RegistrationStatus.CONFIRMED:
            issue_ticket(self.connection, registration_id, received_at)
        record = self._get_owned(registration_id)
        return ApplicationResult(record, existing=False)

    def list_owned(self) -> tuple[Registration, ...]:
        """查看本人报名、候补顺位和取消历史。"""
        require_permission(self.user, Permission.REGISTRATIONS)
        query = (
            REGISTRATION_QUERY + " WHERE record.user_id = ? ORDER BY record.id"
        )
        rows = self.connection.execute(query, (self.user.id,))
        return tuple(registration_from_row(row) for row in rows)

    def ticket(self, registration_id: int) -> Ticket:
        """读取本人报名关联的电子票。"""
        return owned_ticket(self.connection, self.user, registration_id)

    def cancel(self, registration_id: int) -> None:
        """取消本人报名或候补，在有空位时递补一位合格参与者。"""
        require_permission(self.user, Permission.REGISTRATIONS)
        self.connection.execute("BEGIN IMMEDIATE")
        registration = self._get_owned(registration_id)
        if registration.status is RegistrationStatus.CANCELLED:
            return
        if registration.checked_at is not None:
            raise RegistrationError("该报名已签到，无法取消。")

        session = self._get_session(registration.session_id)
        cancelled_at = utc_now()
        if cancelled_at >= datetime.fromisoformat(session["starts_at"]):
            raise RegistrationError("场次已开始，无法取消报名。")

        self.connection.execute(
            "UPDATE registrations SET status = 'cancelled' WHERE id = ?",
            (registration_id,),
        )
        void_ticket(self.connection, registration_id, cancelled_at)
        if (
            registration.status is RegistrationStatus.CONFIRMED
            and session["event_status"] == EventStatus.PUBLISHED.value
        ):
            self._promote_next(
                registration.session_id,
                _campus_only(session["eligibility"]),
                issued_at=cancelled_at,
            )

    def _active_registration_id(self, session_id: int) -> int | None:
        row = self.connection.execute(
            """
            SELECT id FROM registrations
            WHERE user_id = ? AND session_id = ?
              AND status IN ('confirmed', 'waitlisted')
            """,
            (self.user.id, session_id),
        ).fetchone()
        return row["id"] if row is not None else None

    def _get_owned(self, registration_id: int) -> Registration:
        row = self.connection.execute(
            REGISTRATION_QUERY + " WHERE record.id = ? AND record.user_id = ?",
            (registration_id, self.user.id),
        ).fetchone()
        if row is None:
            raise RegistrationError(f"找不到本人报名记录 #{registration_id}。")
        return registration_from_row(row)

    def _get_session(self, session_id: int) -> sqlite3.Row:
        row = self.connection.execute(
            """
            SELECT session.capacity, session.starts_at,
                   session.registration_deadline, event.eligibility,
                   event.status AS event_status
            FROM event_sessions AS session
            JOIN events AS event ON event.id = session.event_id
            WHERE session.id = ?
            """,
            (session_id,),
        ).fetchone()
        if row is None:
            raise RegistrationError(f"找不到场次 #{session_id}。")
        return row

    def _require_category(self, session_id: int, category_id: int) -> None:
        row = self.connection.execute(
            """
            SELECT id FROM registration_categories
            WHERE id = ? AND session_id = ?
            """,
            (category_id, session_id),
        ).fetchone()
        if row is None:
            raise RegistrationError("所选报名类别不属于该场次。")

    def _is_campus_member(self) -> bool:
        row = self.connection.execute(
            "SELECT user_id FROM campus_memberships WHERE user_id = ?",
            (self.user.id,),
        ).fetchone()
        return row is not None

    def _confirmed_count(self, session_id: int) -> int:
        return self.connection.execute(
            """
            SELECT COUNT(*) FROM registrations
            WHERE session_id = ? AND status = 'confirmed'
            """,
            (session_id,),
        ).fetchone()[0]

    def _promote_next(
        self, session_id: int, campus_only: bool, *, issued_at: datetime
    ) -> None:
        candidate = self.connection.execute(
            """
            SELECT record.id
            FROM registrations AS record
            LEFT JOIN campus_memberships AS membership
                ON membership.user_id = record.user_id
            WHERE record.session_id = ? AND record.status = 'waitlisted'
              AND (? = 0 OR membership.user_id IS NOT NULL)
            ORDER BY record.id
            LIMIT 1
            """,
            (session_id, campus_only),
        ).fetchone()
        if candidate is not None:
            self.connection.execute(
                "UPDATE registrations SET status = 'confirmed' WHERE id = ?",
                (candidate["id"],),
            )
            issue_ticket(self.connection, candidate["id"], issued_at)


def utc_now() -> datetime:
    """报名服务使用的服务器时间。"""
    return datetime.now(timezone.utc)


def _campus_only(eligibility: str) -> bool:
    condition = eligibility.strip()
    if condition in ("", "不限"):
        return False
    if condition == "校内师生":
        return True
    raise RegistrationError("系统暂无法核验该活动的报名条件，请联系举办方。")


def registration_from_row(row: sqlite3.Row) -> Registration:
    return Registration(
        id=row["id"],
        session_id=row["session_id"],
        category_id=row["category_id"],
        event_name=row["event_name"],
        session_name=row["session_name"],
        category_name=row["category_name"],
        participant_name=row["participant_name"],
        contact=row["contact"],
        received_at=datetime.fromisoformat(row["received_at"]),
        status=RegistrationStatus(row["status"]),
        waitlist_position=row["waitlist_position"],
        checked_at=parse_optional_time(row["checked_at"]),
    )
