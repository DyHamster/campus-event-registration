"""验证名单、统计、CSV 和审计日志之间的一致性。"""

import csv
import re
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from campus_events.cli import main
from campus_events.database import open_database

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "last-seat.json"
ORGANIZER = ("login", "organizer")
ADMIN = ("login", "admin")
CHECKER = ("login", "checker")


class ReportingWorkflowTest(unittest.TestCase):
    """从演示账号和示例活动开始执行完整的报表工作流。"""

    def setUp(self) -> None:
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.directory = Path(folder.name)
        self.database = self.directory / "reports.sqlite3"
        clock = patch(
            "campus_events.registrations.utc_now",
            return_value=datetime.fromisoformat("2027-03-13T15:00:00+00:00"),
        )
        clock.start()
        self.addCleanup(clock.stop)
        self.run_cli("init", "--demo")
        self.run_cli(*ORGANIZER, "manage-events", "create", str(EXAMPLE))
        self.run_cli(*ORGANIZER, "manage-events", "submit", "1")
        self.run_cli(*ADMIN, "review-events", "approve", "1")

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

    def apply(self, account: str, name: str, contact: str) -> None:
        self.run_cli(
            "login", account, "registrations", "apply", "1", "1",
            "--name", name, "--contact", contact, "--waitlist",
        )

    def prepare_roster(self) -> str:
        self.apply("student", "=1+1", "+86 123")
        self.apply("student2", "参与者乙", "b@example.com")
        self.apply("student3", "参与者丙", "c@example.com")
        self.run_cli("login", "student", "registrations", "cancel", "1")
        participant = ("login", "student2", "registrations")
        ticket = self.run_cli(*participant, "ticket", "2")
        match = re.search(r"^票码：(CE1-[\w-]+)$", ticket, re.MULTILINE)
        if match is None:
            self.fail(ticket)
        self.run_cli(*ADMIN, "checker-access", "grant", "1", "checker")
        code = match.group(1)
        self.run_cli(*CHECKER, "check-in", "verify", "1", "--code", code)
        return code

    def test_export_matches_statistics_and_preserves_history(self) -> None:
        self.prepare_roster()
        roster = (*ORGANIZER, "rosters")
        first = self.run_cli(*roster, "stats", "1")
        for value in ("有效报名：1", "候补：1", "已取消：1", "已签到：1"):
            self.assertIn(value, first)
        second = self.run_cli(*roster, "stats", "2")
        self.assertIn("剩余名额：1", second)
        self.assertIn("有效报名：0", second)
        shown = self.run_cli(
            *roster, "show", "1", "--status", "checked-in", "--search", "乙"
        )
        self.assertIn("1 条报名记录", shown)
        self.assertIn("参与者乙", shown)
        self.assertNotIn("参与者丙", shown)

        destination = self.directory / "roster.csv"
        exported = self.run_cli(*roster, "export", "1", str(destination))
        self.assertIn("已导出 3 条", exported)
        original = destination.read_bytes()
        with destination.open(encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
        self.assertEqual([row["报名编号"] for row in rows], ["1", "2", "3"])
        self.assertEqual(
            [row["报名状态"] for row in rows], ["已取消", "报名成功", "候补中"]
        )
        self.assertEqual(rows[0]["姓名"], "'=1+1")
        self.assertEqual(rows[0]["联系方式"], "'+86 123")
        self.assertTrue(rows[1]["签到时间"])
        self.assertEqual(rows[2]["候补顺位"], "1")
        self.run_cli(*roster, "export", "1", str(destination), status=1)
        self.assertEqual(destination.read_bytes(), original)

        filtered = self.directory / "signed.csv"
        exported = self.run_cli(
            *roster, "export", "1", str(filtered), "--status", "checked-in"
        )
        self.assertIn("已导出 1 条", exported)
        with filtered.open(encoding="utf-8-sig", newline="") as file:
            records = [row["报名编号"] for row in csv.DictReader(file)]
        self.assertEqual(records, ["2"])

        self.run_cli(*ORGANIZER, "manage-events", "cancel", "1")
        history = self.run_cli(*roster, "stats", "1")
        for value in ("有效报名：0", "候补：0", "已取消：3", "已签到：1"):
            self.assertIn(value, history)

    def test_cross_organizer_exports_are_denied_and_audited(self) -> None:
        with open_database(self.database) as connection:
            connection.execute(
                """
                INSERT INTO users (
                    username, name, role, password_salt, password_hash
                )
                SELECT 'other', '其他举办方', role, password_salt, password_hash
                FROM users WHERE username = 'organizer'
                """
            )
        other = ("login", "other", "rosters")
        target = self.directory / "forbidden.csv"
        self.assertIn("暂无场次", self.run_cli(*other, "list"))
        self.assertIn("找不到本人活动", self.run_cli(*other, "show", "1", status=1))
        self.run_cli(*other, "export", "1", str(target), status=1)
        self.assertFalse(target.exists())
        log = self.run_cli(
            *ADMIN, "audit", "--action", "roster.export",
            "--outcome", "rejected",
        )
        self.assertIn("other · roster.export · 场次 #1 · 拒绝或失败", log)
        self.run_cli(*other[:2], "audit", status=1)

    def test_audit_results_do_not_expose_ticket_code(self) -> None:
        code = self.prepare_roster()
        verify = (*CHECKER, "check-in", "verify", "1", "--code")
        self.run_cli(*verify, code)
        self.run_cli(*verify, "invalid", status=1)
        scan_log = self.run_cli(*ADMIN, "audit", "--action", "ticket.check-in")
        for outcome in ("成功", "重复签到", "拒绝或失败"):
            self.assertIn(outcome, scan_log)
        self.assertNotIn(code, scan_log)
        self.assertNotIn("example.com", scan_log)
        reviews = self.run_cli(*ADMIN, "audit", "--action", "event.approve")
        self.assertIn("admin · event.approve · 活动 #1 · 成功", reviews)
        limited = self.run_cli(*ADMIN, "audit", "--limit", "1")
        self.assertEqual(len(limited.splitlines()), 2)
