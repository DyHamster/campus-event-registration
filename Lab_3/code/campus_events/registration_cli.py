"""报名与候补命令的参数和显示。"""

import argparse
from pathlib import Path

from .cli_args import positive_id
from .event_models import CAMPUS_TIME
from .registrations import (
    Registration,
    RegistrationService,
    RegistrationStatus,
)
from .ticket_cli import format_ticket

STATUS_NAMES = {
    RegistrationStatus.CONFIRMED: "报名成功",
    RegistrationStatus.WAITLISTED: "候补中",
    RegistrationStatus.CANCELLED: "已取消",
}


def add_registration_arguments(parser: argparse.ArgumentParser) -> None:
    """添加提交报名、查看记录和取消命令。"""
    actions = parser.add_subparsers(dest="registration_action")
    actions.add_parser("list", help="查看本人的报名与候补记录")
    apply = actions.add_parser("apply", help="报名或在满额时加入候补")
    apply.add_argument("session_id", type=positive_id, help="场次编号")
    apply.add_argument("category_id", type=positive_id, help="报名类别编号")
    apply.add_argument("--name", required=True, help="报名姓名")
    apply.add_argument("--contact", required=True, help="联系方式")
    apply.add_argument(
        "--waitlist", action="store_true", help="名额已满时同意进入候补"
    )
    cancel = actions.add_parser("cancel", help="取消本人报名或候补")
    cancel.add_argument("registration_id", type=positive_id, help="报名记录编号")
    ticket = actions.add_parser("ticket", help="查看或导出本人电子票")
    ticket.add_argument("registration_id", type=positive_id, help="报名记录编号")
    ticket.add_argument("--qr", type=Path, help="导出的 PNG 二维码路径")


def run_registration_command(
    service: RegistrationService, args: argparse.Namespace
) -> str:
    """执行所选操作并返回结果。"""
    match args.registration_action:
        case None | "list":
            records = service.list_owned()
            return "\n\n".join(map(_format_record, records)) or "暂无报名记录。"
        case "apply":
            result = service.apply(
                args.session_id,
                args.category_id,
                name=args.name,
                contact=args.contact,
                join_waitlist=args.waitlist,
            )
            output = _format_record(result.registration)
            if result.existing:
                return f"该场次已有报名或候补记录。\n{output}"
            return output
        case "cancel":
            service.cancel(args.registration_id)
            return f"报名记录 #{args.registration_id} 已取消。"
        case "ticket":
            return format_ticket(service.ticket(args.registration_id), args.qr)
        case _:
            raise ValueError("unsupported registration command")


def _format_record(record: Registration) -> str:
    status = STATUS_NAMES[record.status]
    if record.waitlist_position is not None:
        status += f"（第 {record.waitlist_position} 位）"
    if record.status is RegistrationStatus.CONFIRMED and record.checked_at:
        status = "已签到"
    received = record.received_at.astimezone(CAMPUS_TIME)
    return (
        f"#{record.id} {status} · {record.event_name}\n"
        f"  场次 #{record.session_id} {record.session_name}\n"
        f"  报名类别 #{record.category_id} {record.category_name}\n"
        f"  姓名：{record.participant_name}\n"
        f"  联系方式：{record.contact}\n"
        f"  接收时间：{received.isoformat(sep=' ', timespec='seconds')}"
    )
