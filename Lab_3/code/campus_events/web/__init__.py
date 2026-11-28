"""运行在本机浏览器中的活动报名界面。"""

import hmac
import secrets
from pathlib import Path

from flask import Flask, abort, g, render_template, request, session
from werkzeug.exceptions import HTTPException

from ..access import load_user
from ..database import open_database
from ..event_input import SQLITE_MAX_INTEGER
from .helpers import when, yuan
from .public import public
from .workspaces import workspaces


def create_app(database: Path, *, demo: bool = False) -> Flask:
    """连接既有数据库，注册公开页面和各角色的工作区。"""
    app = Flask(__name__)
    app.config.update(
        DATABASE=database,
        DEMO=demo,
        SECRET_KEY=secrets.token_hex(32),
        SESSION_COOKIE_NAME="campus_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        TRUSTED_HOSTS=["127.0.0.1", "localhost"],
        MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    )
    app.jinja_env.filters.update(when=when, yuan=yuan)
    app.register_blueprint(public)
    app.register_blueprint(workspaces)

    @app.before_request
    def prepare_request() -> None:
        if request.endpoint == "static":
            return
        g.viewer = None
        user_id = session.get("user_id")
        if user_id is not None:
            with open_database(database) as connection:
                g.viewer = load_user(connection, user_id)
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        if request.method == "POST":
            token = request.form.get("csrf", "")
            if not hmac.compare_digest(token.encode(), session["csrf"].encode()):
                abort(400, "表单已过期，请刷新页面后重试。")
        if any(
            isinstance(value, int) and not 0 < value <= SQLITE_MAX_INTEGER
            for value in (request.view_args or {}).values()
        ):
            abort(404)

    @app.after_request
    def protect_private_pages(response):
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; frame-ancestors 'none'; "
            "base-uri 'self'; form-action 'self'"
        )
        return response

    @app.errorhandler(HTTPException)
    def show_error(error: HTTPException):
        return render_template(
            "error.html", title="无法打开页面", status=error.code,
            message=(
                error.description if error.code == 400 else {
                    403: "当前账号没有访问这个页面的权限。",
                    404: "这个页面或记录不存在。",
                    413: "图片或表单太大，请缩小后再试。",
                }.get(error.code, "暂时无法完成此操作，请重试。")
            ),
        ), error.code

    return app
