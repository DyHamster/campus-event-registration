"""活动管理、审核与公开查询。"""

import sqlite3
from datetime import datetime

from .access import Permission, User, require_permission
from .event_models import (
    Event,
    EventDetail,
    EventDraft,
    EventError,
    EventStatus,
    RegistrationCategory,
    Session,
)

EDITABLE = frozenset({EventStatus.DRAFT, EventStatus.REJECTED})


class EventService:
    """对当前用户执行活动操作，由调用者提交或回滚事务。"""

    def __init__(self, connection: sqlite3.Connection, user: User) -> None:
        self.connection = connection
        self.user = user

    def create(self, draft: EventDraft) -> int:
        """创建归属于当前举办方的草稿。"""
        require_permission(self.user, Permission.MANAGE_EVENTS)
        self.connection.execute("BEGIN IMMEDIATE")
        cursor = self.connection.execute(
            """
            INSERT INTO events (
                organizer_id, name, kind, description, eligibility, status
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                self.user.id, draft.name, draft.kind,
                draft.description, draft.eligibility, EventStatus.DRAFT.value,
            ),
        )
        event_id = cursor.lastrowid
        self._save_sessions(event_id, draft.sessions)
        return event_id

    def edit(self, event_id: int, draft: EventDraft) -> None:
        """替换自己的草稿或驳回活动的内容，保留活动编号。"""
        self.connection.execute("BEGIN IMMEDIATE")
        event = self._get_event(Permission.MANAGE_EVENTS, event_id)
        if event.status not in EDITABLE:
            raise EventError("只能编辑草稿或已驳回的活动。")

        self.connection.execute(
            """
            UPDATE events
            SET name = ?, kind = ?, description = ?, eligibility = ?
            WHERE id = ?
            """,
            (
                draft.name, draft.kind, draft.description,
                draft.eligibility, event_id,
            ),
        )
        self.connection.execute(
            "DELETE FROM event_sessions WHERE event_id = ?", (event_id,)
        )
        self._save_sessions(event_id, draft.sessions)

    def submit(self, event_id: int) -> None:
        """将资料齐全的草稿或驳回活动送审。"""
        self.connection.execute("BEGIN IMMEDIATE")
        event = self._get_event(Permission.MANAGE_EVENTS, event_id)
        if event.status not in EDITABLE:
            raise EventError("只能提交草稿或已驳回的活动。")

        sessions = self._get_sessions(event_id)
        if not sessions:
            raise EventError("提交审核前请至少设置一个场次。")
        for session in sessions:
            if not session.categories:
                raise EventError(f"场次「{session.name}」至少需要一个报名类别。")

        self._set_status(event, EventStatus.PENDING, note="")

    def cancel(self, event_id: int) -> None:
        """取消自己的活动并保留记录。"""
        self.connection.execute("BEGIN IMMEDIATE")
        event = self._get_event(Permission.MANAGE_EVENTS, event_id)
        if event.status is EventStatus.CANCELLED:
            raise EventError("该活动已经取消。")
        self.connection.execute(
            """
            UPDATE registrations SET status = 'cancelled'
            WHERE status IN ('confirmed', 'waitlisted')
              AND session_id IN (
                  SELECT id FROM event_sessions WHERE event_id = ?
              )
            """,
            (event_id,),
        )
        self._set_status(event, EventStatus.CANCELLED, note=event.review_note)

    def approve(self, event_id: int) -> None:
        """通过待审活动并立即发布。"""
        self.connection.execute("BEGIN IMMEDIATE")
        event = self._get_event(Permission.REVIEW_EVENTS, event_id)
        self._set_status(event, EventStatus.PUBLISHED, note="")

    def reject(self, event_id: int, reason: str) -> None:
        """驳回待审活动，向举办方保留原因。"""
        self.connection.execute("BEGIN IMMEDIATE")
        event = self._get_event(Permission.REVIEW_EVENTS, event_id)
        reason = reason.strip()
        if not reason:
            raise EventError("请填写驳回原因。")
        self._set_status(event, EventStatus.REJECTED, note=reason)

    def list_events(
        self,
        permission: Permission,
        *,
        search: str | None = None,
        kind: str | None = None,
    ) -> tuple[Event, ...]:
        """按当前入口的可见范围列出活动。"""
        predicate, scope_values = self._scope(permission)
        filters = [predicate]
        values = list(scope_values)
        if search:
            filters.append("instr(lower(name), lower(?)) > 0")
            values.append(search.strip())
        if kind:
            filters.append("kind = ? COLLATE NOCASE")
            values.append(kind.strip())
        where = " AND ".join(filters)
        rows = self.connection.execute(
            f"SELECT * FROM events WHERE {where} ORDER BY id", values
        )
        return tuple(_event(row) for row in rows)

    def detail(self, permission: Permission, event_id: int) -> EventDetail:
        """查询入口可见的活动及其场次，使用同一数据库快照。"""
        self.connection.execute("BEGIN")
        event = self._get_event(permission, event_id)
        return EventDetail(event, self._get_sessions(event.id))

    def _scope(
        self, permission: Permission
    ) -> tuple[str, tuple[int | str, ...]]:
        require_permission(self.user, permission)
        if permission is Permission.MANAGE_EVENTS:
            return "organizer_id = ?", (self.user.id,)
        if permission is Permission.REVIEW_EVENTS:
            return "status = ?", (EventStatus.PENDING.value,)
        if permission is Permission.BROWSE_EVENTS:
            return "status = ?", (EventStatus.PUBLISHED.value,)
        raise ValueError("unsupported event permission")

    def _get_event(self, permission: Permission, event_id: int) -> Event:
        predicate, values = self._scope(permission)
        row = self.connection.execute(
            f"SELECT * FROM events WHERE id = ? AND {predicate}",
            (event_id, *values),
        ).fetchone()
        if row is None:
            raise EventError(f"找不到当前入口可访问的活动 #{event_id}。")
        return _event(row)

    def _get_sessions(self, event_id: int) -> tuple[Session, ...]:
        rows = self.connection.execute(
            """
            SELECT categories.id, categories.name, categories.price_cents,
                   categories.session_id
            FROM registration_categories AS categories
            JOIN event_sessions AS sessions
                ON sessions.id = categories.session_id
            WHERE sessions.event_id = ?
            ORDER BY categories.id
            """,
            (event_id,),
        )
        categories: dict[int, list[RegistrationCategory]] = {}
        for row in rows:
            category = RegistrationCategory(
                name=row["name"], price_cents=row["price_cents"], id=row["id"]
            )
            categories.setdefault(row["session_id"], []).append(category)

        rows = self.connection.execute(
            """
            SELECT session.*, (
                SELECT COUNT(*) FROM registrations
                WHERE session_id = session.id AND status = 'confirmed'
            ) AS confirmed_count
            FROM event_sessions AS session
            WHERE session.event_id = ?
            ORDER BY session.starts_at, session.id
            """,
            (event_id,),
        )
        return tuple(
            Session(
                name=row["name"],
                starts_at=datetime.fromisoformat(row["starts_at"]),
                location=row["location"],
                capacity=row["capacity"],
                registration_deadline=datetime.fromisoformat(
                    row["registration_deadline"]
                ),
                categories=tuple(categories.get(row["id"], ())),
                id=row["id"],
                confirmed_count=row["confirmed_count"],
            )
            for row in rows
        )

    def _save_sessions(
        self, event_id: int, sessions: tuple[Session, ...]
    ) -> None:
        for session in sessions:
            cursor = self.connection.execute(
                """
                INSERT INTO event_sessions (
                    event_id, name, starts_at, location, capacity,
                    registration_deadline
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id, session.name, session.starts_at.isoformat(),
                    session.location, session.capacity,
                    session.registration_deadline.isoformat(),
                ),
            )
            self.connection.executemany(
                """
                INSERT INTO registration_categories (
                    session_id, name, price_cents
                )
                VALUES (?, ?, ?)
                """,
                (
                    (cursor.lastrowid, category.name, category.price_cents)
                    for category in session.categories
                ),
            )

    def _set_status(
        self, event: Event, status: EventStatus, *, note: str
    ) -> None:
        self.connection.execute(
            "UPDATE events SET status = ?, review_note = ? WHERE id = ?",
            (status.value, note, event.id),
        )


def _event(row: sqlite3.Row) -> Event:
    return Event(
        id=row["id"],
        organizer_id=row["organizer_id"],
        name=row["name"],
        kind=row["kind"],
        description=row["description"],
        eligibility=row["eligibility"],
        status=EventStatus(row["status"]),
        review_note=row["review_note"],
    )
