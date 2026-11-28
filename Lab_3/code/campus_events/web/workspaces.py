"""举办方、管理员和检票员的实际业务页面。"""

from flask import Blueprint, Response, abort, flash, g, redirect, render_template, request, url_for

from ..access import Permission, Role
from ..audit import AuditAction, AuditOutcome, recent_entries
from ..check_in import CheckInService
from ..event_models import EventError, EventStatus
from ..events import EDITABLE, EventService
from ..qr_codes import read_qr
from ..rosters import RosterError, RosterService, RosterStatus
from ..tickets import TicketError
from .forms import event_draft, event_fields, read_event_fields
from .helpers import (
    BUSINESS_ERRORS, action_redirect, database, form_id, perform, permitted,
    valid_id, when,
)

workspaces = Blueprint("workspaces", __name__)


@workspaces.get("/organizer")
@permitted(Permission.MANAGE_EVENTS)
def organizer():
    with database() as connection:
        connection.execute("BEGIN")
        events = EventService(connection, g.viewer).list_events(Permission.MANAGE_EVENTS)
        sessions = RosterService(connection, g.viewer).list_sessions()
    return render_template(
        "organizer.html", title="活动管理", events=events, sections=sessions,
        published=sum(event.status is EventStatus.PUBLISHED for event in events),
        pending=sum(event.status is EventStatus.PENDING for event in events),
        confirmed=sum(slot.confirmed for slot in sessions),
        waitlisted=sum(slot.waitlisted for slot in sessions),
    )


@workspaces.get("/organizer/<int:event_id>")
@permitted(Permission.MANAGE_EVENTS)
def owned_event(event_id: int):
    detail = _detail(Permission.MANAGE_EVENTS, event_id)
    return render_template("owned.html", title=detail.event.name, detail=detail)


@workspaces.route("/organizer/new", methods=["GET", "POST"])
@workspaces.route("/organizer/<int:event_id>/edit", methods=["GET", "POST"])
@permitted(Permission.MANAGE_EVENTS)
def editor(event_id=None):
    detail = _detail(Permission.MANAGE_EVENTS, event_id) if event_id else None
    if detail and detail.event.status not in EDITABLE:
        abort(403)
    fields = event_fields(detail)
    error = None
    if request.method == "POST":
        action = AuditAction.EVENT_EDIT if event_id else AuditAction.EVENT_CREATE

        def save(connection):
            service = EventService(connection, g.viewer)
            draft = event_draft(fields)
            if event_id is not None:
                service.edit(event_id, draft)
                return event_id
            return service.create(draft)

        try:
            fields = read_event_fields(request.form)
            saved_id = perform(save, audit=(action, event_id))
        except BUSINESS_ERRORS as failure:
            error = str(failure)
        else:
            flash("活动草稿已保存。", "success")
            return redirect(url_for("workspaces.owned_event", event_id=saved_id))
    return render_template(
        "editor.html", title="编辑活动" if event_id else "创建活动",
        fields=fields, error=error,
    ), 400 if error else 200


@workspaces.post("/organizer/<int:event_id>/<any(submit,cancel):action>")
@permitted(Permission.MANAGE_EVENTS)
def owner_action(event_id: int, action: str):
    audit_action = AuditAction.EVENT_SUBMIT if action == "submit" else AuditAction.EVENT_CANCEL

    def change(connection):
        service = EventService(connection, g.viewer)
        if action == "submit":
            service.submit(event_id)
        else:
            service.cancel(event_id)

    return action_redirect(
        change, url_for("workspaces.owned_event", event_id=event_id),
        "活动已提交审核。" if action == "submit" else "活动已取消。",
        audit=(audit_action, event_id),
    )


@workspaces.get("/review")
@permitted(Permission.REVIEW_EVENTS)
def review():
    with database() as connection:
        events = EventService(connection, g.viewer).list_events(Permission.REVIEW_EVENTS)
    selected = valid_id(request.args.get("event"))
    detail = _detail(Permission.REVIEW_EVENTS, selected or events[0].id) if events else None
    return render_template("review.html", title="活动审核", events=events, detail=detail)


@workspaces.post("/review/<int:event_id>/<any(approve,reject):action>")
@permitted(Permission.REVIEW_EVENTS)
def review_action(event_id: int, action: str):
    approve = action == "approve"

    def change(connection):
        service = EventService(connection, g.viewer)
        if approve:
            service.approve(event_id)
        else:
            service.reject(event_id, request.form.get("reason", ""))

    return action_redirect(
        change, url_for("workspaces.review"),
        "审核通过，活动已发布。" if approve else "活动已驳回。",
        audit=(AuditAction.EVENT_APPROVE if approve else AuditAction.EVENT_REJECT, event_id),
    )


@workspaces.get("/rosters")
@permitted(Permission.ROSTERS)
def rosters():
    with database() as connection:
        connection.execute("BEGIN")
        service = RosterService(connection, g.viewer)
        sessions = service.list_sessions()
        current = valid_id(request.args.get("session"))
        stats = next(
            (item for item in sessions if item.session_id == current),
            sessions[0] if current is None and sessions else None,
        )
        if stats is None and current is not None:
            abort(404)
        search = request.args.get("q", "")
        status = _filter(RosterStatus, request.args.get("status"))
        records = service.list_records(
            stats.session_id, search=search, status=status
        ) if stats else ()
    return render_template(
        "rosters.html", title="名单与统计", sessions=sessions, stats=stats,
        records=records, search=search, selected_status=status,
    )


@workspaces.post("/rosters/<int:session_id>/export")
@permitted(Permission.ROSTERS)
def roster_export(session_id: int):
    status = _filter(RosterStatus, request.form.get("status"))
    try:
        data, _ = perform(lambda connection: RosterService(
            connection, g.viewer
        ).export_csv(session_id, search=request.form.get("q"), status=status),
            audit=(AuditAction.ROSTER_EXPORT, session_id),
        )
    except RosterError:
        abort(404)
    return Response(
        data, content_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="roster-{session_id}.csv"'},
    )


@workspaces.route("/check-in", methods=["GET", "POST"])
@permitted(Permission.CHECK_IN)
def check_in():
    if request.method == "POST":
        session_id = form_id(request.form.get("session"))

        def verify(connection):
            code = request.form.get("code", "").strip()
            upload = request.files.get("qr")
            if code and upload and upload.filename:
                raise TicketError("请选择一种检票方式。")
            if upload and upload.filename:
                code = read_qr(upload.stream)
            if not code:
                raise TicketError("请输入票码或上传二维码图片。")
            return CheckInService(connection, g.viewer).verify(session_id, code)

        try:
            result = perform(verify, audit=(AuditAction.CHECK_IN, session_id))
        except BUSINESS_ERRORS as error:
            flash(str(error), "error")
        else:
            if result.duplicate:
                flash(f"已签到。首次签到时间 {when(result.checked_at)}。", "success")
            else:
                flash(f"签到成功。{result.participant_name} · {when(result.checked_at)}。", "success")
        return redirect(url_for("workspaces.check_in", session=session_id))

    assigned = perform(lambda connection: CheckInService(connection, g.viewer).own_sessions())
    return render_template(
        "check-in.html", title="现场检票", sessions=assigned,
        selected=valid_id(request.args.get("session")),
    )


@workspaces.get("/checker-access")
@permitted(Permission.CHECKER_ACCESS)
def checker_access():
    with database() as connection:
        assigned = CheckInService(connection, g.viewer).list_assignments()
        sessions = connection.execute(
            """
            SELECT session.id, session.name, event.name AS event_name
            FROM event_sessions AS session JOIN events AS event ON event.id = session.event_id
            WHERE event.status = ? ORDER BY session.id
            """, (EventStatus.PUBLISHED.value,),
        ).fetchall()
        checkers = connection.execute(
            "SELECT username, name FROM users WHERE role = ? ORDER BY username",
            (Role.CHECKER.value,),
        ).fetchall()
    return render_template(
        "access.html", title="检票授权", assigned=assigned, sessions=sessions, checkers=checkers,
    )


@workspaces.post("/checker-access/<any(grant,revoke):action>")
@permitted(Permission.CHECKER_ACCESS)
def change_access(action: str):
    session_id = form_id(request.form.get("session"))
    username = request.form.get("checker", "")

    def change(connection):
        service = CheckInService(connection, g.viewer)
        if action == "grant":
            service.grant(session_id, username)
        else:
            service.revoke(session_id, username)

    return action_redirect(
        change, url_for("workspaces.checker_access"),
        "检票权限已授予。" if action == "grant" else "检票权限已撤销。",
        audit=(AuditAction.CHECKER_GRANT if action == "grant" else AuditAction.CHECKER_REVOKE, session_id),
    )


@workspaces.get("/audit")
@permitted(Permission.AUDIT)
def audit():
    action = _filter(AuditAction, request.args.get("action"))
    outcome = _filter(AuditOutcome, request.args.get("outcome"))
    entries = perform(lambda connection: recent_entries(
        connection, g.viewer, action=action, outcome=outcome
    ))
    return render_template(
        "audit.html", title="操作日志", entries=entries, actions=tuple(AuditAction),
        action=action, outcome=outcome,
    )


def _detail(permission: Permission, event_id: int):
    try:
        return perform(lambda connection: EventService(
            connection, g.viewer
        ).detail(permission, event_id))
    except EventError:
        abort(404)


def _filter(values, requested):
    try:
        return values(requested) if requested else None
    except ValueError:
        abort(400, "筛选条件无效。")
