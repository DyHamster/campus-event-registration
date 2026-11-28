"""启动本地浏览器界面。"""

import argparse
from pathlib import Path

from ..cli import DEFAULT_DATABASE
from . import create_app
from .demo import prepare_database


def main() -> None:
    parser = argparse.ArgumentParser(description="集会 · 本地校园活动报名界面")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--demo", action="store_true", help="启用演示账号和活动")
    args = parser.parse_args()
    if not 0 < args.port <= 65535:
        parser.error("端口必须在 1 至 65535 之间")
    prepare_database(args.database, demo=args.demo)
    create_app(args.database, demo=args.demo).run(
        host="127.0.0.1", port=args.port, debug=False
    )


if __name__ == "__main__":
    main()
