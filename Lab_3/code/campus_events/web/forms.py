"""将浏览器的活动表单转换成现有活动草稿。"""

import re
from decimal import Decimal, InvalidOperation

from ..event_input import SQLITE_MAX_INTEGER, parse_draft
from ..event_models import EventError
from .helpers import when


def event_fields(detail=None) -> dict:
    if detail is None:
        return {
            "name": "", "kind": "", "description": "", "eligibility": "",
            "sessions": [],
        }
    event = detail.event
    return {
        "name": event.name, "kind": event.kind, "description": event.description,
        "eligibility": event.eligibility,
        "sessions": [
            {
                "key": str(index), "name": slot.name, "location": slot.location,
                "capacity": str(slot.capacity), "starts_at": when(slot.starts_at, "form"),
                "registration_deadline": when(slot.registration_deadline, "form"),
                "categories": [
                    {"name": item.name, "price": (
                        f"{item.price_cents // 100}.{item.price_cents % 100:02d}"
                    )} for item in slot.categories
                ],
            }
            for index, slot in enumerate(detail.sessions, start=1)
        ],
    }


def read_event_fields(form) -> dict:
    """读取用户输入，验证失败时保留原表单。"""
    fields = {
        key: form.get(key, "") for key in ("name", "kind", "description", "eligibility")
    }
    keys = form.getlist("session_key")
    if len(keys) != len(set(keys)) or any(not re.fullmatch(r"[0-9]{1,8}", key) for key in keys):
        raise EventError("场次表单有重复或无效的编号。")
    sessions = []
    for key in keys:
        slot = {
            field: form.get(f"s{key}_{field}", "") for field in (
                "name", "location", "capacity", "starts_at", "registration_deadline"
            )
        }
        names = form.getlist(f"s{key}_category")
        prices = form.getlist(f"s{key}_price")
        if len(names) != len(prices):
            raise EventError("请填写每个报名类别的名称和票价。")
        slot.update(key=key, categories=[
            {"name": name, "price": price} for name, price in zip(names, prices)
        ])
        sessions.append(slot)
    fields["sessions"] = sessions
    return fields


def event_draft(fields: dict):
    sessions = []
    for slot in fields["sessions"]:
        try:
            capacity = int(slot["capacity"])
        except ValueError as error:
            raise EventError("场次容量必须填写正整数。") from error
        sessions.append({
            "name": slot["name"], "location": slot["location"], "capacity": capacity,
            "starts_at": _local_time(slot["starts_at"]),
            "registration_deadline": _local_time(slot["registration_deadline"]),
            "categories": [
                {"name": item["name"], "price_cents": _price(item["price"])}
                for item in slot["categories"]
            ],
        })
    return parse_draft({**fields, "sessions": sessions})


def _local_time(value: str) -> str:
    if not value:
        raise EventError("请填写场次开始时间和报名截止时间。")
    return f"{value}+08:00"


def _price(value: str) -> int:
    try:
        value_in_yuan = Decimal(value)
    except InvalidOperation as error:
        raise EventError("票价必须填写有效金额。") from error
    if (
        not value_in_yuan.is_finite()
        or value_in_yuan < 0
        or value_in_yuan > Decimal(SQLITE_MAX_INTEGER) / 100
    ):
        raise EventError("票价应为非负金额，并在系统支持范围内。")
    cents = value_in_yuan * 100
    if cents != cents.to_integral_value():
        raise EventError("票价最多保留两位小数。")
    return int(cents)
