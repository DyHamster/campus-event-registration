"""活动命令的参数和终端输出。"""

import argparse
from pathlib import Path

from .access import Permission
from .cli_args import positive_id
from .event_input import read_draft
from .event_models import CAMPUS_TIME, Event, EventDetail, EventStatus
from .events import EventService

STATUS_NAMES = {
    EventStatus.DRAFT: "草稿",
    EventStatus.PENDING: "待审核",
    EventStatus.REJECTED: "已驳回",
    EventStatus.PUBLISHED: "已发布",
    EventStatus.CANCELLED: "已取消",
}


def add_event_arguments(
    parser: argparse.ArgumentParser, permission: Permission
) -> None:
    """添加该角色入口下的活动操作。"""
    parser.set_defaults(search=None, kind=None)
    actions = parser.add_subparsers(dest="event_action")
    list_command = actions.add_parser("list", help="列出活动")
    show = actions.add_parser("show", help="查看活动及其场次")
    show.add_argument("event_id", type=positive_id, help="活动编号")

    if permission is Permission.BROWSE_EVENTS:
        list_command.add_argument("--search", help="按活动名称搜索")
        list_command.add_argument("--kind", help="按活动分类筛选")
    elif permission is Permission.MANAGE_EVENTS:
        create = actions.add_parser("create", help="从 JSON 创建活动草稿")
        create.add_argument("file", type=Path, help="活动配置文件")
        edit = actions.add_parser("edit", help="从 JSON 更新活动草稿")
        edit.add_argument("event_id", type=positive_id, help="活动编号")
        edit.add_argument("file", type=Path, help="活动配置文件")
        submit = actions.add_parser("submit", help="提交活动审核")
        submit.add_argument("event_id", type=positive_id, help="活动编号")
        cancel = actions.add_parser("cancel", help="取消活动")
        cancel.add_argument("event_id", type=positive_id, help="活动编号")
    elif permission is Permission.REVIEW_EVENTS:
        approve = actions.add_parser("approve", help="通过审核并发布活动")
        approve.add_argument("event_id", type=positive_id, help="活动编号")
        reject = actions.add_parser("reject", help="驳回活动")
        reject.add_argument("event_id", type=positive_id, help="活动编号")
        reject.add_argument("--reason", required=True, help="驳回原因")


def run_event_command(
    service: EventService, permission: Permission, args: argparse.Namespace
) -> str:
    """执行活动操作，返回提交事务后可显示的结果。"""
    match args.event_action:
        case None | "list":
            events = service.list_events(
                permission, search=args.search, kind=args.kind
            )
            return "\n".join(_event_line(event) for event in events) or "暂无活动。"
        case "show":
            return _detail_text(service.detail(permission, args.event_id))
        case "create":
            event_id = service.create(read_draft(args.file))
            return f"已创建活动 #{event_id}（草稿）。"
        case "edit":
            service.edit(args.event_id, read_draft(args.file))
            return f"已更新活动 #{args.event_id}。"
        case "submit":
            service.submit(args.event_id)
            return f"活动 #{args.event_id} 已提交审核。"
        case "cancel":
            service.cancel(args.event_id)
            return f"活动 #{args.event_id} 已取消。"
        case "approve":
            service.approve(args.event_id)
            return f"活动 #{args.event_id} 已发布。"
        case "reject":
            service.reject(args.event_id, args.reason)
            return f"活动 #{args.event_id} 已驳回。"
        case _:
            raise ValueError("unsupported event command")


def _event_line(event: Event) -> str:
    status = STATUS_NAMES[event.status]
    return f"#{event.id} {event.name} · {event.kind} · {status}"


def _detail_text(detail: EventDetail) -> str:
    event = detail.event
    lines = [
        _event_line(event),
        f"介绍：{event.description or '暂无'}",
        f"报名条件：{event.eligibility or '不限'}",
    ]
    if event.review_note:
        lines.append(f"驳回原因：{event.review_note}")
    lines.append("场次（北京时间）：")
    if not detail.sessions:
        lines.append("  暂无场次。")

    for session in detail.sessions:
        start = session.starts_at.astimezone(CAMPUS_TIME)
        deadline = session.registration_deadline.astimezone(CAMPUS_TIME)
        lines.extend(
            [
                f"  #{session.id} {session.name}",
                f"    时间：{start.isoformat(sep=' ')}",
                f"    地点：{session.location}",
                f"    容量：{session.capacity} 人",
                f"    剩余名额：{session.capacity - session.confirmed_count} 人",
                f"    报名截止：{deadline.isoformat(sep=' ')}",
            ]
        )
        if not session.categories:
            lines.append("    暂无报名类别。")
        for category in session.categories:
            yuan, cents = divmod(category.price_cents, 100)
            lines.append(
                f"    报名类别 #{category.id} {category.name}：¥{yuan}.{cents:02d}"
            )
    return "\n".join(lines)
