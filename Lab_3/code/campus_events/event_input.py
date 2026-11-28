"""读取并校验举办方的活动配置文件。"""

import json
from datetime import datetime, timezone
from pathlib import Path

from .event_models import (
    CAMPUS_TIME,
    EventDraft,
    EventError,
    RegistrationCategory,
    Session,
)

SQLITE_MAX_INTEGER = (1 << 63) - 1


def read_draft(path: Path) -> EventDraft:
    """从 UTF-8 JSON 读取活动草稿，拒绝无法保存的字段。"""
    try:
        source = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as error:
        raise EventError("活动配置文件必须使用 UTF-8 编码。") from error
    except json.JSONDecodeError as error:
        raise EventError(
            f"JSON 格式错误（第 {error.lineno} 行第 {error.colno} 列）。"
        ) from error
    except ValueError as error:
        raise EventError("活动配置文件含超出解析范围的数值。") from error
    return parse_draft(source)


def parse_draft(source: object) -> EventDraft:
    """校验活动草稿，供命令行和网页表单共同使用。"""
    draft = _object(
        source,
        "活动",
        ("name", "kind", "description", "eligibility", "sessions"),
    )
    return EventDraft(
        name=_text(draft.get("name"), "name"),
        kind=_text(draft.get("kind"), "kind"),
        description=_text(
            draft.get("description", ""), "description", required=False
        ),
        eligibility=_text(
            draft.get("eligibility", ""), "eligibility", required=False
        ),
        sessions=_sessions(draft.get("sessions", [])),
    )


def _sessions(value: object) -> tuple[Session, ...]:
    if not isinstance(value, list):
        raise EventError("sessions 必须是数组。")
    sessions = tuple(
        _session(item, f"sessions[{index}]")
        for index, item in enumerate(value)
    )
    if len({session.name for session in sessions}) != len(sessions):
        raise EventError("同一活动中的场次名称不能重复。")
    return sessions


def _session(value: object, field: str) -> Session:
    data = _object(
        value,
        field,
        (
            "name", "starts_at", "location", "capacity",
            "registration_deadline", "categories",
        ),
    )
    starts_at = _time(data.get("starts_at"), f"{field}.starts_at")
    deadline = _time(
        data.get("registration_deadline"), f"{field}.registration_deadline"
    )
    if deadline >= starts_at:
        raise EventError(f"{field} 的报名截止时间必须早于活动开始时间。")

    return Session(
        name=_text(data.get("name"), f"{field}.name"),
        starts_at=starts_at,
        location=_text(data.get("location"), f"{field}.location"),
        capacity=_integer(
            data.get("capacity"), f"{field}.capacity", minimum=1
        ),
        registration_deadline=deadline,
        categories=_categories(
            data.get("categories", []), f"{field}.categories"
        ),
    )


def _categories(value: object, field: str) -> tuple[RegistrationCategory, ...]:
    if not isinstance(value, list):
        raise EventError(f"{field} 必须是数组。")
    categories = []
    for index, item in enumerate(value):
        label = f"{field}[{index}]"
        data = _object(item, label, ("name", "price_cents"))
        categories.append(
            RegistrationCategory(
                name=_text(data.get("name"), f"{label}.name"),
                price_cents=_integer(
                    data.get("price_cents"), f"{label}.price_cents", minimum=0
                ),
            )
        )
    if len({category.name for category in categories}) != len(categories):
        raise EventError(f"{field} 的报名类别名称不能重复。")
    return tuple(categories)


def _object(
    value: object, field: str, allowed: tuple[str, ...]
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise EventError(f"{field} 必须是 JSON 对象。")
    unknown = sorted(value.keys() - allowed)
    if unknown:
        raise EventError(f"{field} 含未知字段：{', '.join(unknown)}。")
    return value


def _text(value: object, field: str, *, required: bool = True) -> str:
    if not isinstance(value, str):
        raise EventError(f"{field} 必须是文本。")
    value = value.strip()
    if required and not value:
        raise EventError(f"{field} 不能为空。")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise EventError(f"{field} 含无效字符。") from error
    return value


def _integer(value: object, field: str, *, minimum: int) -> int:
    if type(value) is not int or not minimum <= value <= SQLITE_MAX_INTEGER:
        raise EventError(
            f"{field} 必须是 {minimum} 到 {SQLITE_MAX_INTEGER} 之间的整数。"
        )
    return value


def _time(value: object, field: str) -> datetime:
    text = _text(value, field)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        timestamp = datetime.fromisoformat(text)
        if timestamp.utcoffset() is None:
            raise ValueError("missing time zone")
        utc = timestamp.astimezone(timezone.utc)
        utc.astimezone(CAMPUS_TIME)
    except (ValueError, OverflowError) as error:
        raise EventError(
            f"{field} 必须是带时区的时间，例如 2027-03-14T14:00:00+08:00。"
        ) from error
    return utc
