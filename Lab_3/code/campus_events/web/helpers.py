"""网页共用的数据库、权限、时间和表单辅助函数。"""

from collections.abc import Callable
from datetime import datetime
from functools import wraps

from flask import abort, current_app, flash, g, redirect, url_for

from ..access import Permission, require_permission
from ..audit import AuditAction, AuditOutcome, record_audit
from ..database import open_database
from ..event_input import SQLITE_MAX_INTEGER
from ..event_models import CAMPUS_TIME, EventError
from ..registrations import RegistrationError
from ..rosters import RosterError
from ..tickets import TicketError

BUSINESS_ERRORS = (EventError, RegistrationError, RosterError, TicketError, OSError)


def database():
    return open_database(current_app.config["DATABASE"])


def permitted(permission: Permission):
    """验证浏览器会话和业务权限。"""
    def decorate(handler: Callable):
        @wraps(handler)
        def wrapped(*args, **kwargs):
            if g.viewer is None:
                return redirect(url_for("public.login"))
            try:
                require_permission(g.viewer, permission)
            except PermissionError:
                abort(403)
            return handler(*args, **kwargs)

        return wrapped

    return decorate


def perform(operation: Callable, *, audit: tuple[AuditAction, int | None] | None = None):
    """提交业务操作，失败时独立记录对应的审计结果。"""
    try:
        with database() as connection:
            return operation(connection)
    except BUSINESS_ERRORS:
        if audit is not None:
            with database() as connection:
                record_audit(
                    connection, g.viewer, *audit, outcome=AuditOutcome.REJECTED
                )
        raise


def action_redirect(
    operation: Callable, destination: str, success: str, *,
    audit: tuple[AuditAction, int | None] | None = None,
):
    try:
        perform(operation, audit=audit)
    except BUSINESS_ERRORS as error:
        flash(str(error), "error")
    else:
        flash(success, "success")
    return redirect(destination)


def valid_id(value: str | int | None) -> int | None:
    try:
        number = int(value)
    except (ValueError, TypeError):
        return None
    return number if 0 < number <= SQLITE_MAX_INTEGER else None


def form_id(value: str | None) -> int:
    number = valid_id(value)
    if number is None:
        abort(400, "请选择有效的场次或报名类别。")
    return number


def when(value: datetime | None, style: str = "full") -> str:
    if value is None:
        return "—"
    local = value.astimezone(CAMPUS_TIME)
    if style == "short":
        return local.strftime("%m月%d日 %H:%M")
    if style == "form":
        return local.replace(tzinfo=None).isoformat()
    return local.strftime("%Y年%m月%d日 %H:%M")


def yuan(cents: int) -> str:
    return "免费" if cents == 0 else f"¥{cents // 100}.{cents % 100:02d}"
