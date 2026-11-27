"""电子票、检票和授权命令。"""

import argparse
from datetime import datetime
from pathlib import Path

from .check_in import CheckerAssignment, CheckInService
from .cli_args import positive_id
from .event_models import CAMPUS_TIME
from .qr_codes import read_qr, save_qr
from .tickets import Ticket, TicketError, TicketStatus

TICKET_STATUS_NAMES = {
    TicketStatus.VALID: "有效",
    TicketStatus.CHECKED_IN: "已签到",
    TicketStatus.VOID: "已作废",
}


def add_check_in_arguments(parser: argparse.ArgumentParser) -> None:
    """添加查看授权场次及核验票据的命令。"""
    actions = parser.add_subparsers(dest="check_in_action")
    actions.add_parser("list", help="列出本人获授权的检票场次")
    verify = actions.add_parser("verify", help="核验电子票并签到")
    verify.add_argument("session_id", type=positive_id, help="场次编号")
    source = verify.add_mutually_exclusive_group()
    source.add_argument("--qr", type=Path, help="包含二维码的 PNG 或 JPEG")
    source.add_argument("--code", help="电子票票码")


def add_checker_access_arguments(parser: argparse.ArgumentParser) -> None:
    """添加授予和撤销场次检票权限的命令。"""
    actions = parser.add_subparsers(dest="checker_access_action")
    actions.add_parser("list", help="列出检票授权")
    for action, help_text in (("grant", "授予场次授权"), ("revoke", "撤销场次授权")):
        command = actions.add_parser(action, help=help_text)
        command.add_argument("session_id", type=positive_id, help="场次编号")
        command.add_argument("checker", help="检票员用户名")


def run_check_in_command(
    service: CheckInService, args: argparse.Namespace
) -> str:
    """展示检票场次，或使用指定来源的票码核验电子票。"""
    if args.check_in_action != "verify":
        return _assignments_text(service.own_sessions())

    if args.qr is not None:
        code = read_qr(args.qr)
    elif args.code is not None:
        code = args.code
    else:
        code = input("请扫描二维码或输入票码：")
    result = service.verify(args.session_id, code)
    time = _timestamp(result.checked_at)
    if result.duplicate:
        return f"已签到。首次签到时间：{time}"
    return (
        f"签到成功。场次 #{result.session_id} · 报名 #{result.registration_id}\n"
        f"参与者：{result.participant_name}\n"
        f"签到时间：{time}"
    )


def run_checker_access_command(
    service: CheckInService, args: argparse.Namespace
) -> str:
    """查看或变更检票授权。"""
    match args.checker_access_action:
        case None | "list":
            return _assignments_text(service.list_assignments())
        case "grant":
            service.grant(args.session_id, args.checker)
            return f"已授权 {args.checker} 核验场次 #{args.session_id}。"
        case "revoke":
            service.revoke(args.session_id, args.checker)
            return f"已撤销 {args.checker} 对场次 #{args.session_id} 的授权。"
        case _:
            raise ValueError("unsupported checker access command")


def format_ticket(ticket: Ticket, qr_path: Path | None) -> str:
    """展示电子票信息，按需导出可扫码的 PNG。"""
    lines = [
        f"电子票 · 报名 #{ticket.registration_id}",
        f"活动：{ticket.event_name}",
        f"场次 #{ticket.session_id} {ticket.session_name}",
        f"时间：{_timestamp(ticket.starts_at)}",
        f"地点：{ticket.location}",
        f"状态：{TICKET_STATUS_NAMES[ticket.status]}",
    ]
    if ticket.checked_at is not None:
        lines.append(f"首次签到时间：{_timestamp(ticket.checked_at)}")
    if ticket.status is TicketStatus.VOID:
        if qr_path is not None:
            raise TicketError("电子票已作废，无法导出二维码。")
    else:
        lines.append(f"票码：{ticket.code}")
        if qr_path is not None:
            save_qr(ticket.code, qr_path)
            lines.append(f"二维码已保存到：{qr_path}")
    return "\n".join(lines)


def _timestamp(timestamp: datetime) -> str:
    return timestamp.astimezone(CAMPUS_TIME).isoformat(
        sep=" ", timespec="seconds"
    )


def _assignments_text(assignments: tuple[CheckerAssignment, ...]) -> str:
    return "\n".join(
        f"#{item.session_id} {item.event_name} · {item.session_name}"
        f" · {item.location} · {item.checker_username}"
        for item in assignments
    ) or "暂无检票授权。"
