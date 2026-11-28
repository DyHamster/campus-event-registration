"""查看举办方的场次统计，按报名状态筛选并导出名单。"""

import csv
import os
import sqlite3
from dataclasses import dataclass
from enum import Enum
from io import StringIO
from pathlib import Path
from tempfile import NamedTemporaryFile

from .access import Permission, User, require_permission
from .audit import AuditAction, record_audit
from .event_models import CAMPUS_TIME, EventStatus
from .registrations import (
    REGISTRATION_QUERY,
    STATUS_NAMES,
    Registration,
    registration_from_row,
)


class RosterError(Exception):
    """场次不存在或超出举办方可访问范围。"""


class RosterStatus(str, Enum):
    """报名状态或已签到筛选条件。"""

    CONFIRMED = "confirmed"
    WAITLISTED = "waitlisted"
    CANCELLED = "cancelled"
    CHECKED_IN = "checked-in"


@dataclass(frozen=True, slots=True)
class SessionStats:
    """同一场次的容量、有效报名、候补、取消及历史签到人数。"""

    session_id: int
    event_id: int
    event_name: str
    session_name: str
    status: EventStatus
    capacity: int
    confirmed: int
    waitlisted: int
    cancelled: int
    checked_in: int

    @property
    def available(self) -> int:
        if self.status is EventStatus.PUBLISHED:
            return self.capacity - self.confirmed
        return 0


STATS_QUERY = """
    SELECT session.id AS session_id, session.event_id, event.name AS event_name,
           session.name AS session_name, event.status, session.capacity,
           COUNT(CASE WHEN record.status = 'confirmed' THEN 1 END)
               AS confirmed,
           COUNT(CASE WHEN record.status = 'waitlisted' THEN 1 END)
               AS waitlisted,
           COUNT(CASE WHEN record.status = 'cancelled' THEN 1 END)
               AS cancelled,
           COUNT(check_in.ticket_id) AS checked_in
    FROM event_sessions AS session
    JOIN events AS event ON event.id = session.event_id
    LEFT JOIN registrations AS record ON record.session_id = session.id
    LEFT JOIN tickets AS ticket ON ticket.registration_id = record.id
    LEFT JOIN check_ins AS check_in ON check_in.ticket_id = ticket.id
    WHERE event.organizer_id = ?
"""

CSV_HEADER = (
    "报名编号", "活动", "场次编号", "场次", "报名类别",
    "姓名", "联系方式", "报名状态", "候补顺位", "签到时间",
)


class RosterService:
    """只允许举办方访问本人活动的统计和报名资料。"""

    def __init__(self, connection: sqlite3.Connection, user: User) -> None:
        self.connection = connection
        self.user = user

    def list_sessions(self) -> tuple[SessionStats, ...]:
        """列出本人活动下的全部场次统计。"""
        require_permission(self.user, Permission.ROSTERS)
        rows = self.connection.execute(
            STATS_QUERY + " GROUP BY session.id ORDER BY session.id",
            (self.user.id,),
        )
        return tuple(_stats(row) for row in rows)

    def stats(self, session_id: int) -> SessionStats:
        """在授权范围内读取一个场次的统计。"""
        require_permission(self.user, Permission.ROSTERS)
        return self._stats_for_session(session_id)

    def list_records(
        self,
        session_id: int,
        *,
        status: RosterStatus | None,
        search: str | None,
    ) -> tuple[Registration, ...]:
        """查询并筛选一个场次的报名记录。"""
        require_permission(self.user, Permission.ROSTERS)
        if not self.connection.in_transaction:
            self.connection.execute("BEGIN")
        self._stats_for_session(session_id)
        return self._records(session_id, status=status, search=search)

    def export(
        self,
        session_id: int,
        path: Path,
        *,
        status: RosterStatus | None,
        search: str | None,
    ) -> int:
        """保存筛选后的 CSV，返回导出的报名数。"""
        data, count = self.export_csv(session_id, status=status, search=search)
        _write_csv(path, data)
        return count

    def export_csv(
        self,
        session_id: int,
        *,
        status: RosterStatus | None,
        search: str | None,
    ) -> tuple[bytes, int]:
        """生成可下载的 CSV 内容，并记录导出操作。"""
        require_permission(self.user, Permission.ROSTERS)
        self.connection.execute("BEGIN IMMEDIATE")
        self._stats_for_session(session_id)
        records = self._records(session_id, status=status, search=search)
        with StringIO(newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(CSV_HEADER)
            writer.writerows(_csv_row(record) for record in records)
            data = stream.getvalue().encode("utf-8-sig")
        record_audit(
            self.connection, self.user, AuditAction.ROSTER_EXPORT, session_id
        )
        return data, len(records)

    def _stats_for_session(self, session_id: int) -> SessionStats:
        row = self.connection.execute(
            STATS_QUERY + " AND session.id = ? GROUP BY session.id",
            (self.user.id, session_id),
        ).fetchone()
        if row is None:
            raise RosterError(f"找不到本人活动的场次 #{session_id}。")
        return _stats(row)

    def _records(
        self,
        session_id: int,
        *,
        status: RosterStatus | None,
        search: str | None,
    ) -> tuple[Registration, ...]:
        filters = ["record.session_id = ?"]
        values: list[int | str] = [session_id]
        if status is RosterStatus.CHECKED_IN:
            filters.append("check_in.checked_at IS NOT NULL")
        elif status is not None:
            filters.append("record.status = ?")
            values.append(status.value)
        if search:
            filters.append(
                "instr(lower(record.participant_name), lower(?)) > 0"
            )
            values.append(search.strip())

        where = " AND ".join(filters)
        query = f"{REGISTRATION_QUERY} WHERE {where} ORDER BY record.id"
        rows = self.connection.execute(query, values)
        return tuple(registration_from_row(row) for row in rows)


def _stats(row: sqlite3.Row) -> SessionStats:
    return SessionStats(
        session_id=row["session_id"],
        event_id=row["event_id"],
        event_name=row["event_name"],
        session_name=row["session_name"],
        status=EventStatus(row["status"]),
        capacity=row["capacity"],
        confirmed=row["confirmed"],
        waitlisted=row["waitlisted"],
        cancelled=row["cancelled"],
        checked_in=row["checked_in"],
    )


def check_in_time(record: Registration) -> str:
    """场次名单统一显示北京时间。"""
    if record.checked_at is None:
        return ""
    return record.checked_at.astimezone(CAMPUS_TIME).isoformat(
        sep=" ", timespec="seconds"
    )


def _write_csv(path: Path, data: bytes) -> None:
    temp_path = None
    try:
        with NamedTemporaryFile(
            mode="wb", dir=path.parent,
            prefix=".roster-", delete=False,
        ) as stream:
            temp_path = Path(stream.name)
            stream.write(data)
        os.link(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _csv_row(record: Registration) -> tuple[int | str | None, ...]:
    return (
        record.id, _csv_text(record.event_name), record.session_id,
        _csv_text(record.session_name), _csv_text(record.category_name),
        _csv_text(record.participant_name), _csv_text(record.contact),
        STATUS_NAMES[record.status], record.waitlist_position,
        check_in_time(record),
    )


def _csv_text(value: str) -> str:
    """让表格软件把可能被识别为公式的用户输入当作文本。"""
    if value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(
        ("=", "+", "-", "@", "＝", "＋", "－", "＠")
    ):
        return "'" + value
    return value
