"""命令行入口，负责登录和访问角色对应的业务入口。"""

import argparse
import sqlite3
import sys
import warnings
from getpass import GetPassWarning, getpass
from pathlib import Path

from .access import (
    AuthenticationError,
    Permission,
    Role,
    authenticate,
    permissions_for,
    require_permission,
)
from .database import create_schema, open_database
from .demo import seed_demo_accounts

DEFAULT_DATABASE = Path("data/campus_events.sqlite3")
ROLE_NAMES = {
    Role.PARTICIPANT: "普通参与者",
    Role.ORGANIZER: "活动举办方",
    Role.ADMIN: "平台管理员",
    Role.CHECKER: "现场检票人员",
}
ENTRY_NAMES = {
    Permission.BROWSE_EVENTS: "公开活动",
    Permission.MANAGE_EVENTS: "活动管理",
    Permission.REVIEW_EVENTS: "活动审核",
    Permission.CHECK_IN: "检票签到",
}


def build_parser() -> argparse.ArgumentParser:
    """定义数据库初始化和登录命令。"""
    parser = argparse.ArgumentParser(
        prog="campus_events", description="校园活动票务与报名系统"
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE,
        help=f"数据库路径，默认 {DEFAULT_DATABASE}",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="初始化数据库")
    init.add_argument("--demo", action="store_true", help="添加四类本地演示账号")

    login = commands.add_parser("login", help="登录并查看或进入业务功能")
    login.add_argument("username", help="账号名")
    login.add_argument(
        "entry",
        nargs="?",
        choices=[permission.value for permission in Permission],
        help="要进入的功能，省略时列出当前账号可访问的功能",
    )
    return parser


def initialize(path: Path, demo: bool) -> None:
    """在同一事务中创建用户表并初始化演示数据。"""
    with open_database(path, create=True) as connection:
        connection.execute("BEGIN IMMEDIATE")
        create_schema(connection)
        if demo:
            added = seed_demo_accounts(connection)
    print(f"数据库已初始化：{path}")
    if demo:
        print(f"新增演示账号 {added} 个。")


def login(path: Path, username: str, entry: str | None) -> None:
    """验证账号后展示可访问入口，或检查并进入指定功能。"""
    if not path.exists():
        raise FileNotFoundError(f"数据库不存在，请先运行 init：{path}")

    with open_database(path) as connection:
        with warnings.catch_warnings():
            warnings.simplefilter("error", GetPassWarning)
            password = getpass("密码：")
        user = authenticate(connection, username, password)

    if entry is not None:
        permission = Permission(entry)
        require_permission(user, permission)
        print(f"已进入「{ENTRY_NAMES[permission]}」。")
        return

    print(f"已登录：{user.name}（{ROLE_NAMES[user.role]}）")
    print("可访问的功能：")
    for permission in permissions_for(user):
        print(f"  {permission.value:16} {ENTRY_NAMES[permission]}")


def main(argv: list[str] | None = None) -> int:
    """执行命令并将操作错误报告给终端。"""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            initialize(args.database, args.demo)
        else:
            login(args.database, args.username, args.entry)
    except GetPassWarning:
        print("请在支持隐藏密码输入的终端中运行登录命令。", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\n操作已取消。", file=sys.stderr)
        return 130
    except (AuthenticationError, OSError, sqlite3.Error) as error:
        print(f"操作失败：{error}", file=sys.stderr)
        return 1
    return 0
