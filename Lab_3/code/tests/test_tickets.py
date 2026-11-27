"""检验出票、授权、签到和二维码在真实数据库中的集成。"""

import re
import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, redirect_stderr, redirect_stdout
from datetime import datetime, timedelta
from importlib.util import find_spec
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import patch

from campus_events.access import Role, User
from campus_events.check_in import CheckInService
from campus_events.cli import main
from campus_events.database import open_database

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "last-seat.json"
CHECK_TIME = datetime.fromisoformat("2027-03-14T05:30:00+00:00")
SIGNUP_TIME = datetime.fromisoformat("2027-03-13T15:00:00+00:00")
QR_AVAILABLE = (
    find_spec("PIL") is not None and find_spec("zxingcpp") is not None
)


class TicketWorkflowTest(unittest.TestCase):
    """在独立数据库中发布含两个场次的示例活动。"""

    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.database = self.directory / "campus.sqlite3"
        clock = patch(
            "campus_events.registrations.utc_now", return_value=SIGNUP_TIME
        )
        clock.start()
        self.addCleanup(clock.stop)

        self.run_cli("init", "--demo")
        manage = ("login", "organizer", "manage-events")
        self.run_cli(*manage, "create", str(EXAMPLE))
        self.run_cli(*manage, "submit", "1")
        self.run_cli("login", "admin", "review-events", "approve", "1")

    def run_cli(self, *args: str, status: int = 0) -> str:
        stdout, stderr = StringIO(), StringIO()
        with (
            redirect_stdout(stdout),
            redirect_stderr(stderr),
            patch("campus_events.cli.getpass", return_value="campus-demo"),
        ):
            result = main(["--database", str(self.database), *args])
        self.assertEqual(result, status, stdout.getvalue() + stderr.getvalue())
        return stdout.getvalue() if status == 0 else stderr.getvalue()

    def apply(self, account: str) -> str:
        return self.run_cli(
            "login", account, "registrations", "apply", "1", "1", "--waitlist",
            "--name", account, "--contact", "demo@example.com",
        )

    def ticket(self, account: str, record: str, *, status: int = 0) -> str:
        return self.run_cli(
            "login", account, "registrations", "ticket", record, status=status
        )

    def code(self, account: str, record: str) -> str:
        output = self.ticket(account, record)
        match = re.search(r"^票码：(CE1-[\w-]+)$", output, re.MULTILINE)
        if match is None:
            self.fail(output)
        return match.group(1)

    def grant(self, session: str) -> None:
        entry = ("login", "admin", "checker-access")
        self.run_cli(*entry, "grant", session, "checker")

    def verify(self, session: str, code: str, *, status: int = 0) -> str:
        return self.run_cli(
            "login", "checker", "check-in", "verify", session, "--code", code,
            status=status,
        )

    def test_issue_void_and_promotion(self) -> None:
        self.assertIn("报名成功", self.apply("student"))
        code = self.code("student", "1")
        self.assertIn("已有报名或候补记录", self.apply("student"))
        self.assertEqual(self.code("student", "1"), code)

        self.assertIn("候补中", self.apply("student2"))
        self.assertIn("暂无电子票", self.ticket("student2", "2", status=1))
        self.assertIn("找不到本人", self.ticket("student2", "1", status=1))
        self.grant("1")
        self.run_cli("login", "student", "registrations", "cancel", "1")

        old_ticket = self.ticket("student", "1")
        self.assertIn("已作废", old_ticket)
        self.assertNotIn(code, old_ticket)
        self.assertIn("电子票已失效", self.verify("1", code, status=1))
        promoted = self.code("student2", "2")
        self.assertNotEqual(promoted, code)
        self.assertIn("签到成功", self.verify("1", promoted))

    def test_check_in_scope_and_repeated_scan(self) -> None:
        self.apply("student")
        code = self.code("student", "1")
        self.assertIn("未获该场次", self.verify("1", code, status=1))
        self.grant("2")
        self.assertIn("不属于当前场次", self.verify("2", code, status=1))
        self.assertIn("未获该场次", self.verify("1", code, status=1))
        self.grant("1")
        assigned = self.run_cli("login", "checker", "check-in", "list")
        self.assertIn("午后场", assigned)
        self.assertIn("票码无效", self.verify("1", "invalid", status=1))

        with patch("campus_events.check_in.utc_now", return_value=CHECK_TIME):
            self.assertIn("签到成功", self.verify("1", code))
        later = CHECK_TIME + timedelta(minutes=1)
        with patch("campus_events.check_in.utc_now", return_value=later):
            repeated = self.verify("1", code)
        self.assertIn("首次签到时间：2027-03-14 13:30:00+08:00", repeated)
        self.assertIn("已签到", self.ticket("student", "1"))
        error = self.run_cli(
            "login", "student", "registrations", "cancel", "1", status=1
        )
        self.assertIn("已签到，无法取消", error)
        admin = ("login", "admin", "checker-access")
        self.run_cli(*admin, "revoke", "1", "checker")
        self.assertIn("未获该场次", self.verify("1", code, status=1))

    def test_event_cancellation_preserves_check_in_history(self) -> None:
        self.apply("student")
        self.grant("1")
        code = self.code("student", "1")
        self.verify("1", code)
        self.run_cli("login", "organizer", "manage-events", "cancel", "1")

        cancelled = self.ticket("student", "1")
        self.assertIn("已作废", cancelled)
        self.assertIn("首次签到时间", cancelled)
        self.assertIn("电子票已失效", self.verify("1", code, status=1))
        self.assertIn(
            "暂无检票授权", self.run_cli("login", "checker", "check-in", "list")
        )

    def test_upgrade_backfills_only_confirmed_tickets(self) -> None:
        self.apply("student")
        self.apply("student2")
        with closing(sqlite3.connect(self.database)) as connection:
            with connection:
                for table in ("check_ins", "session_checkers", "tickets"):
                    connection.execute(f"DROP TABLE {table}")
                connection.execute("PRAGMA user_version = 3")

        self.run_cli("init")
        code = self.code("student", "1")
        self.assertIn("暂无电子票", self.ticket("student2", "2", status=1))
        self.run_cli("init", "--demo")
        self.assertEqual(code, self.code("student", "1"))

    def test_concurrent_verifications_record_one_check_in(self) -> None:
        self.apply("student")
        self.grant("1")
        code = self.code("student", "1")
        with open_database(self.database) as connection:
            row = connection.execute(
                "SELECT id, name FROM users WHERE username = 'checker'"
            ).fetchone()
        checker = User(row["id"], "checker", row["name"], Role.CHECKER)
        ready = Barrier(2, timeout=5)

        def verify() -> tuple[bool, datetime]:
            ready.wait()
            with open_database(self.database) as connection:
                result = CheckInService(connection, checker).verify(1, code)
                return result.duplicate, result.checked_at

        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = (pool.submit(verify) for _ in range(2))
            results = [first.result(), second.result()]
        self.assertEqual(sorted(item[0] for item in results), [False, True])
        self.assertEqual(results[0][1], results[1][1])
        with open_database(self.database) as connection:
            query = "SELECT COUNT(*) FROM check_ins"
            count = connection.execute(query).fetchone()
        self.assertEqual(count[0], 1)

    @unittest.skipUnless(QR_AVAILABLE, "请先安装 requirements.txt 的二维码依赖")
    def test_export_and_scan_png(self) -> None:
        self.apply("student")
        self.grant("1")
        image = self.directory / "ticket.png"
        export = ("login", "student", "registrations", "ticket", "1", "--qr")
        self.assertIn("二维码已保存", self.run_cli(*export, str(image)))
        original = image.read_bytes()
        self.run_cli(*export, str(image), status=1)
        self.assertEqual(image.read_bytes(), original)

        scan = ("login", "checker", "check-in", "verify", "1", "--qr")
        self.assertIn("签到成功", self.run_cli(*scan, str(image)))
        self.assertIn("首次签到时间", self.run_cli(*scan, str(image)))
        bad_image = self.directory / "bad.png"
        bad_image.write_bytes(b"not an image")
        error = self.run_cli(*scan, str(bad_image), status=1)
        self.assertIn("无法读取二维码", error)
