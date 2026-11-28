"""活动广场、登录、报名和个人电子票。"""

from datetime import datetime, timezone

from flask import (
    Blueprint, Response, abort, current_app, flash, g, redirect, render_template,
    request, session, url_for,
)

from ..access import AuthenticationError, Permission, Role, authenticate
from ..event_models import EventDetail, EventError
from ..events import EventService
from ..qr_codes import qr_png
from ..registrations import RegistrationService, RegistrationStatus
from ..tickets import TicketError, TicketStatus
from .helpers import (
    BUSINESS_ERRORS, action_redirect, database, form_id, perform, permitted,
    valid_id,
)

public = Blueprint("public", __name__)
ROLE_DESTINATIONS = {
    Role.ORGANIZER: "workspaces.organizer",
    Role.ADMIN: "workspaces.review",
    Role.CHECKER: "workspaces.check_in",
}
ART = {
    "文艺演出": "music",
    "学术讲座": "lecture",
    "运动健康": "sports",
    "社团活动": "clubs",
}


@public.get("/")
def catalog():
    keyword = request.args.get("q", "").strip()
    kind = request.args.get("kind", "").strip()
    with database() as connection:
        service = EventService(connection, g.viewer)
        all_events = service.catalog()

    now = datetime.now(timezone.utc)
    visible = [
        _card(detail, now) for detail in all_events
        if (not keyword or _matches(detail, keyword))
        and (not kind or detail.event.kind == kind)
    ]
    types = sorted({detail.event.kind for detail in all_events})
    open_count = sum(card["open"] for card in visible)
    return render_template(
        "catalog.html", title="发现活动", cards=visible, types=types,
        active_kind=kind, keyword=keyword, open_count=open_count,
    )


@public.get("/events/<int:event_id>")
def event(event_id: int):
    try:
        detail = perform(lambda connection: EventService(
            connection, g.viewer
        ).detail(Permission.BROWSE_EVENTS, event_id))
    except EventError:
        abort(404)

    now = datetime.now(timezone.utc)
    requested = valid_id(request.args.get("session"))
    chosen = next((slot for slot in detail.sessions if slot.id == requested), None)
    card = _card(detail, now)
    if chosen is None:
        chosen = card["slot"]
    can_register = g.viewer is not None and g.viewer.role is Role.PARTICIPANT
    return render_template(
        "event.html", title=detail.event.name, detail=detail,
        chosen=chosen, now=now, art=card["art"],
        can_register=can_register,
    )


@public.post("/events/<int:event_id>/register")
@permitted(Permission.REGISTRATIONS)
def register(event_id: int):
    session_id = form_id(request.form.get("session"))
    category_id = form_id(request.form.get("category"))

    def submit(connection):
        if connection.execute(
            "SELECT 1 FROM event_sessions WHERE id = ? AND event_id = ?",
            (session_id, event_id),
        ).fetchone() is None:
            abort(404)
        return RegistrationService(connection, g.viewer).apply(
            session_id, category_id,
            name=request.form.get("name", ""),
            contact=request.form.get("contact", ""),
            join_waitlist="waitlist" in request.form,
        )

    try:
        result = perform(submit)
    except BUSINESS_ERRORS as error:
        flash(str(error), "error")
        return redirect(url_for("public.event", event_id=event_id, session=session_id))
    if result.existing:
        message = "该场次已有报名或候补记录。"
    elif result.registration.status is RegistrationStatus.WAITLISTED:
        message = f"已加入候补，当前第 {result.registration.waitlist_position} 位。"
    else:
        message = "报名成功，电子票已发放。"
    flash(message, "success")
    return redirect(url_for("public.my_events"))


@public.get("/my")
@permitted(Permission.REGISTRATIONS)
def my_events():
    records = perform(lambda connection: RegistrationService(
        connection, g.viewer
    ).list_owned())
    return render_template("my.html", title="我的活动", records=records)


@public.post("/my/<int:registration_id>/cancel")
@permitted(Permission.REGISTRATIONS)
def cancel_registration(registration_id: int):
    return action_redirect(
        lambda connection: RegistrationService(
            connection, g.viewer
        ).cancel(registration_id),
        url_for("public.my_events"), "报名记录已取消。",
    )


@public.get("/tickets/<int:registration_id>")
@permitted(Permission.REGISTRATIONS)
def ticket(registration_id: int):
    try:
        info = _ticket(registration_id)
    except TicketError as error:
        flash(str(error), "error")
        return redirect(url_for("public.my_events"))
    return render_template("ticket.html", title="电子票", ticket=info)


@public.get("/tickets/<int:registration_id>/qr.png")
@permitted(Permission.REGISTRATIONS)
def ticket_qr(registration_id: int):
    try:
        info = _ticket(registration_id)
        if info.status is TicketStatus.VOID:
            abort(404)
        return Response(qr_png(info.code), mimetype="image/png")
    except TicketError:
        abort(404)


@public.route("/login", methods=["GET", "POST"])
def login():
    event_id = valid_id(request.values.get("event"))
    session_id = valid_id(request.values.get("session"))
    name = ""
    error = None
    if request.method == "POST":
        name = request.form.get("username", "").strip()
        try:
            user = perform(lambda connection: authenticate(
                connection, name, request.form.get("password", "")
            ))
        except AuthenticationError as failure:
            error = str(failure)
        else:
            session.clear()
            session["user_id"] = user.id
            if event_id is not None:
                return redirect(url_for(
                    "public.event", event_id=event_id, session=session_id
                ))
            return redirect(url_for(ROLE_DESTINATIONS.get(user.role, "public.catalog")))
    elif current_app.config["DEMO"]:
        name = request.args.get("account", "")

    return render_template(
        "login.html", title="登录集会", username=name, event_id=event_id,
        session_id=session_id, error=error, demo=current_app.config["DEMO"],
    ), 401 if error else 200


@public.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("public.catalog"))


def _ticket(registration_id: int):
    return perform(lambda connection: RegistrationService(
        connection, g.viewer
    ).ticket(registration_id))


def _card(detail: EventDetail, now: datetime) -> dict:
    open_slots = [slot for slot in detail.sessions if slot.registration_deadline > now]
    slot = next(iter(open_slots or detail.sessions), None)
    price = min(
        (choice.price_cents for choice in slot.categories), default=None
    ) if slot else None
    return {
        "detail": detail,
        "slot": slot,
        "open": bool(open_slots),
        "price": price,
        "art": ART.get(detail.event.kind, "clubs"),
    }


def _matches(detail: EventDetail, keyword: str) -> bool:
    word = keyword.casefold()
    fields = (detail.event.name, detail.event.kind, *(slot.location for slot in detail.sessions))
    return any(word in field.casefold() for field in fields)
