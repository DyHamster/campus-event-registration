"""通过命令行验证活动状态、公开范围和旧数据库升级。"""

import json
import sqlite3
import unittest
from contextlib import closing, redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from campus_events.cli import main

EXAMPLE = (
    Path(__file__).resolve().parents[1] / "examples" / "campus-lecture.json"
)


class EventWorkflowTest(unittest.TestCase):
    """每项测试使用独立数据库及真实演示账号。"""

    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.database = self.directory / "test.sqlite3"
        self.success("init", "--demo")

    def invoke(self, *args: str) -> tuple[int, str, str]:
        stdout, stderr = StringIO(), StringIO()
        with (
            redirect_stdout(stdout),
            redirect_stderr(stderr),
            patch("campus_events.cli.getpass", return_value="campus-demo"),
        ):
            code = main(["--database", str(self.database), *args])
        return code, stdout.getvalue(), stderr.getvalue()

    def success(self, *args: str) -> str:
        code, output, error = self.invoke(*args)
        self.assertEqual(code, 0, error)
        return output

    def failure(self, *args: str) -> str:
        code, output, error = self.invoke(*args)
        self.assertEqual(code, 1, output)
        self.assertEqual(output, "")
        return error

    def write_draft(self, value: dict[str, object]) -> str:
        path = self.directory / "draft.json"
        source = json.dumps(value, ensure_ascii=False)
        path.write_text(source, encoding="utf-8")
        return str(path)

    def test_draft_review_publish_and_cancel(self) -> None:
        manage = ("login", "organizer", "manage-events")
        review = ("login", "admin", "review-events")
        browse = ("login", "student", "browse-events")

        output = self.success(*manage, "create", str(EXAMPLE))
        self.assertIn("#1（草稿）", output)
        self.assertNotIn("校园摄影讲座", self.success(*browse, "list"))
        self.assertIn("找不到", self.failure(*browse, "show", "1"))

        self.success(*manage, "submit", "1")
        self.assertIn("校园摄影讲座", self.success(*review, "list"))
        self.assertNotIn("校园摄影讲座", self.success(*browse, "list"))
        self.assertIn("找不到", self.failure(*browse, "show", "1"))
        self.assertIn(
            "只能编辑草稿或已驳回", self.failure(*manage, "edit", "1", str(EXAMPLE))
        )

        self.success(*review, "reject", "1", "--reason", "请更新场地")
        self.assertIn("请更新场地", self.success(*manage, "show", "1"))
        self.assertNotIn("校园摄影讲座", self.success(*review, "list"))
        self.assertNotIn("校园摄影讲座", self.success(*browse, "list"))

        edited = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        edited["sessions"][0]["location"] = "图书馆 B203"
        edited["sessions"][0]["capacity"] = 12
        self.success(*manage, "edit", "1", self.write_draft(edited))
        self.success(*manage, "submit", "1")
        self.success(*review, "approve", "1")
        self.assertIn("找不到", self.failure(*review, "approve", "1"))

        output = self.success(
            *browse, "list", "--search", "摄影", "--kind", "讲座"
        )
        self.assertIn("校园摄影讲座", output)
        self.assertNotIn(
            "校园摄影讲座", self.success(*browse, "list", "--kind", "演出")
        )
        self.assertNotIn(
            "校园摄影讲座", self.success(*browse, "list", "--search", "%")
        )
        detail = self.success(*browse, "show", "1")
        for text in (
            "校内师生", "午后场", "图书馆 B203", "12 人", "¥12.50",
            "傍晚场", "教学楼 A202", "20 人", "15:00:00+08:00",
        ):
            with self.subTest(text=text):
                self.assertIn(text, detail)
        self.assertNotIn("请更新场地", detail)
        self.assertIn(
            "只能编辑草稿或已驳回", self.failure(*manage, "edit", "1", str(EXAMPLE))
        )

        self.success(*manage, "cancel", "1")
        self.assertIn("已取消", self.success(*manage, "show", "1"))
        self.assertNotIn("校园摄影讲座", self.success(*browse, "list"))
        self.assertIn("找不到", self.failure(*browse, "show", "1"))

    def test_organizers_cannot_access_each_others_activities(self) -> None:
        with closing(sqlite3.connect(self.database)) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO users (
                        username, name, role, password_salt, password_hash
                    )
                    SELECT 'other', '其他举办方', role, password_salt,
                           password_hash
                    FROM users
                    WHERE username = 'organizer'
                    """
                )
        owner = ("login", "organizer", "manage-events")
        other = ("login", "other", "manage-events")
        self.success(*owner, "create", str(EXAMPLE))
        self.assertNotIn("校园摄影讲座", self.success(*other, "list"))
        for action in ("show", "edit", "submit", "cancel"):
            with self.subTest(action=action):
                arguments = (str(EXAMPLE),) if action == "edit" else ()
                self.assertIn(
                    "找不到", self.failure(*other, action, "1", *arguments)
                )
        self.assertIn("草稿", self.success(*owner, "show", "1"))

    def test_incomplete_or_invalid_draft_cannot_be_published(self) -> None:
        manage = ("login", "organizer", "manage-events")
        empty_draft = self.write_draft({"name": "占位活动", "kind": "讲座"})
        self.success(*manage, "create", empty_draft)
        self.assertIn("至少设置一个场次", self.failure(*manage, "submit", "1"))

        draft = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        first = draft["sessions"][0]
        first["registration_deadline"] = "2027-03-14T06:00:00Z"
        self.assertIn(
            "截止时间必须早于",
            self.failure(*manage, "edit", "1", self.write_draft(draft)),
        )
        self.assertIn("暂无场次", self.success(*manage, "show", "1"))

        first["registration_deadline"] = "2027-03-14T05:00:00Z"
        first["categories"] = []
        self.success(*manage, "edit", "1", self.write_draft(draft))
        error = self.failure(*manage, "submit", "1")
        self.assertIn("至少需要一个报名类别", error)

    def test_upgrade_preserves_stage_one_accounts(self) -> None:
        with closing(sqlite3.connect(self.database)) as connection:
            with connection:
                connection.execute("DROP TABLE registration_categories")
                connection.execute("DROP TABLE event_sessions")
                connection.execute("DROP TABLE events")
                connection.execute("PRAGMA user_version = 0")
            query = "SELECT * FROM users ORDER BY id"
            accounts_before = connection.execute(query).fetchall()

            manage = ("login", "organizer", "manage-events")
            self.assertIn("请先运行 init", self.failure(*manage, "list"))
            self.success("init")
            self.assertEqual(
                accounts_before, connection.execute(query).fetchall()
            )

        self.assertIn("暂无活动", self.success(*manage, "list"))
        self.success(*manage, "create", str(EXAMPLE))
        self.success("init", "--demo")
        self.assertIn("校园摄影讲座", self.success(*manage, "list"))
