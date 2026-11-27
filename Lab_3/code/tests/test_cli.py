"""通过命令入口验证初始化、登录和角色权限。"""

import sqlite3
import unittest
from contextlib import closing, redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from campus_events.cli import main


class CampusEventsCliTest(unittest.TestCase):
    """验证不同账号从同一入口执行操作的结果。"""

    @classmethod
    def setUpClass(cls) -> None:
        directory = TemporaryDirectory()
        cls.addClassCleanup(directory.cleanup)
        cls.database = Path(directory.name) / "campus.sqlite3"
        with redirect_stdout(StringIO()):
            result = main(["--database", str(cls.database), "init", "--demo"])
        if result != 0:
            raise RuntimeError("无法初始化测试数据库")

    def run_cli(
        self,
        *args: str,
        path: Path | None = None,
        password: str = "campus-demo",
    ) -> tuple[int, str, str]:
        stdout = StringIO()
        stderr = StringIO()
        database = self.database if path is None else path
        with (
            redirect_stdout(stdout),
            redirect_stderr(stderr),
            patch("campus_events.cli.getpass", return_value=password),
        ):
            result = main(["--database", str(database), *args])
        return result, stdout.getvalue(), stderr.getvalue()

    def test_role_access_matrix(self) -> None:
        access = {
            "student": {"browse-events", "registrations"},
            "organizer": {"browse-events", "manage-events", "rosters"},
            "admin": {
                "browse-events", "review-events", "checker-access", "audit",
            },
            "checker": {"browse-events", "check-in"},
        }
        entries = (
            "browse-events", "manage-events", "review-events", "check-in",
            "registrations", "checker-access", "rosters", "audit",
        )
        for username, allowed in access.items():
            for entry in entries:
                with self.subTest(username=username, entry=entry):
                    code, stdout, stderr = self.run_cli(
                        "login", username, entry
                    )
                    if entry in allowed:
                        self.assertEqual(code, 0)
                        message = (
                            "暂无报名记录" if entry == "registrations" else "已进入"
                        )
                        self.assertIn(message, stdout)
                        self.assertEqual(stderr, "")
                    else:
                        self.assertEqual(code, 1)
                        self.assertIn("没有权限", stderr)
                        self.assertEqual(stdout, "")

    def test_invalid_credentials_cannot_enter_a_function(self) -> None:
        wrong_password = self.run_cli(
            "login", "organizer", "manage-events", password="incorrect"
        )
        unknown_user = self.run_cli("login", "unknown", "manage-events")
        self.assertEqual(wrong_password, unknown_user)
        self.assertEqual(wrong_password[0:2], (1, ""))
        self.assertIn("用户名或密码不正确", wrong_password[2])

    def test_initialization_preserves_existing_accounts(self) -> None:
        with closing(sqlite3.connect(self.database)) as connection:
            query = "SELECT * FROM users ORDER BY id"
            before = connection.execute(query).fetchall()
            code, stdout, _ = self.run_cli("init", "--demo")
            after = connection.execute(query).fetchall()

        self.assertEqual(code, 0)
        self.assertIn("新增演示账号 0 个", stdout)
        self.assertEqual(len(after), 7)
        self.assertEqual(before, after)

    def test_plain_initialization_does_not_add_demo_users(self) -> None:
        path = self.database.with_name("empty.sqlite3")
        code, _, _ = self.run_cli("init", path=path)
        self.assertEqual(code, 0)
        with closing(sqlite3.connect(path)) as connection:
            count = connection.execute("SELECT COUNT(*) FROM users").fetchone()
            self.assertEqual(count, (0,))

    def test_login_does_not_create_a_database(self) -> None:
        path = self.database.with_name("missing.sqlite3")
        code, stdout, stderr = self.run_cli("login", "student", path=path)
        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("请先运行 init", stderr)
        self.assertFalse(path.exists())
