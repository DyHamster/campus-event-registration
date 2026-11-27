"""举办方名单和管理员操作日志的命令行入口。"""

import argparse
import sqlite3
from pathlib import Path

from .access import User
from .audit import AuditAction, AuditOutcome, recent_entries, record_audit
from .cli_args import positive_id
from .event_cli import STATUS_NAMES as EVENT_NAMES
from .event_models import CAMPUS_TIME
from .registrations import STATUS_NAMES as REGISTRATION_NAMES
from .rosters import RosterService, RosterStatus, SessionStats, check_in_time

OUTCOME_NAMES = {
    AuditOutcome.SUCCESS: "成功",
    AuditOutcome.REJECTED: "拒绝或失败",
    AuditOutcome.DUPLICATE: "重复签到",
}

EVENT_ACTIONS = {
    "create": AuditAction.EVENT_CREATE,
    "edit": AuditAction.EVENT_EDIT,
    "submit": AuditAction.EVENT_SUBMIT,
    "approve": AuditAction.EVENT_APPROVE,
    "reject": AuditAction.EVENT_REJECT,
    "cancel": AuditAction.EVENT_CANCEL,
}


def add_roster_arguments(parser: argparse.ArgumentParser) -> None:
    """添加名单查询、容量统计及导出命令。"""
    actions = parser.add_subparsers(dest="roster_action")
    actions.add_parser("list", help="查看本人活动的全部场次统计")
    stats = actions.add_parser("stats", help="查看指定场次的统计")
    stats.add_argument("session_id", type=positive_id, help="场次编号")
    show = actions.add_parser("show", help="查看指定场次的名单")
    export = actions.add_parser("export", help="导出指定场次的名单为 CSV")
    for command in (show, export):
        command.add_argument("session_id", type=positive_id, help="场次编号")
        command.add_argument("--search", help="按参与者姓名搜索")
        command.add_argument(
            "--status",
            choices=[status.value for status in RosterStatus],
            help="筛选报名状态或已签到记录",
        )
    export.add_argument("output", type=Path, help="新 CSV 文件路径")


def add_audit_arguments(parser: argparse.ArgumentParser) -> None:
    """添加操作日志查询选项。"""
    parser.add_argument(
        "--action", choices=[item.value for item in AuditAction]
    )
    parser.add_argument(
        "--outcome", choices=[item.value for item in AuditOutcome]
    )
    parser.add_argument("--limit", type=positive_id, default=50)


def run_roster_command(
    service: RosterService, args: argparse.Namespace
) -> str:
    """执行名单和统计命令。"""
    action = args.roster_action
    if action is None or action == "list":
        summaries = map(_format_stats, service.list_sessions())
        return "\n\n".join(summaries) or "暂无场次。"
    if action == "stats":
        return _format_stats(service.stats(args.session_id))

    status = RosterStatus(args.status) if args.status else None
    if action == "export":
        count = service.export(
            args.session_id, args.output, status=status, search=args.search
        )
        return f"已导出 {count} 条报名记录到：{args.output}"

    records = service.list_records(
        args.session_id, status=status, search=args.search
    )
    lines = [f"场次 #{args.session_id} · {len(records)} 条报名记录"]
    for record in records:
        fields = [
            f"#{record.id} {record.participant_name}",
            record.category_name,
            REGISTRATION_NAMES[record.status],
            f"联系方式：{record.contact}",
        ]
        if record.waitlist_position is not None:
            fields.append(f"候补第 {record.waitlist_position} 位")
        if record.checked_at is not None:
            fields.append(f"签到：{check_in_time(record)}")
        lines.append(" · ".join(fields))
    return "\n".join(lines)


def run_audit_command(
    connection: sqlite3.Connection, user: User, args: argparse.Namespace
) -> str:
    """展示关键操作的时间、操作者、目标和结果。"""
    entries = recent_entries(
        connection,
        user,
        action=AuditAction(args.action) if args.action else None,
        outcome=AuditOutcome(args.outcome) if args.outcome else None,
        limit=args.limit,
    )
    lines = []
    for entry in entries:
        date = entry.occurred_at.astimezone(CAMPUS_TIME).isoformat(
            sep=" ", timespec="seconds"
        )
        fields = [f"#{entry.id} {date}", entry.actor, entry.action.value]
        if entry.target_id is not None:
            target = "活动" if entry.action.value.startswith("event.") else "场次"
            fields.append(f"{target} #{entry.target_id}")
        fields.append(OUTCOME_NAMES[entry.outcome])
        lines.append(" · ".join(fields))
    return "\n".join(lines) or "暂无操作日志。"


def audit_failed_command(
    connection: sqlite3.Connection, user: User, args: argparse.Namespace
) -> None:
    """先回滚业务写入，再单独记录被拒绝的关键命令。"""
    action = None
    target = None
    if args.entry in ("manage-events", "review-events"):
        action = EVENT_ACTIONS.get(args.event_action)
        target = getattr(args, "event_id", None)
    elif args.entry == "checker-access":
        action = {
            "grant": AuditAction.CHECKER_GRANT,
            "revoke": AuditAction.CHECKER_REVOKE,
        }.get(args.checker_access_action)
        target = getattr(args, "session_id", None)
    elif args.entry == "check-in" and args.check_in_action == "verify":
        action, target = AuditAction.CHECK_IN, args.session_id
    elif args.entry == "rosters" and args.roster_action == "export":
        action, target = AuditAction.ROSTER_EXPORT, args.session_id

    if action is not None:
        connection.rollback()
        with connection:
            record_audit(
                connection, user, action, target, outcome=AuditOutcome.REJECTED
            )


def _format_stats(stats: SessionStats) -> str:
    return (
        f"场次 #{stats.session_id} {stats.event_name} · {stats.session_name}"
        f" · {EVENT_NAMES[stats.status]}\n"
        f"容量：{stats.capacity} · 剩余名额：{stats.available}"
        f" · 有效报名：{stats.confirmed} · 候补：{stats.waitlisted}"
        f" · 已取消：{stats.cancelled} · 已签到：{stats.checked_in}"
    )
