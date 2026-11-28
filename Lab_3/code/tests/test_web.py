"""验证四类账号在网页上使用同一套业务数据。"""

import csv
import re
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from html import unescape
from importlib.util import find_spec
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from campus_events.event_models import CAMPUS_TIME

WEB_AVAILABLE = find_spec("flask") is not None
QR_AVAILABLE = find_spec("PIL") is not None and find_spec("zxingcpp") is not None

if WEB_AVAILABLE:
    from campus_events.web import create_app
    from campus_events.web.demo import prepare_database


@unittest.skipUnless(WEB_AVAILABLE, "网页测试需要安装 Flask")
class CampusWebTest(unittest.TestCase):
    def setUp(self) -> None:
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.database = Path(folder.name) / "demo.sqlite3"
        with redirect_stdout(StringIO()):
            prepare_database(self.database, demo=True)
        self.app = create_app(self.database, demo=True)
        self.app.testing = True

    def post(self, client, url, **form):
        with client.session_transaction() as state:
            form["csrf"] = state["csrf"]
        return client.post(url, data=form, follow_redirects=True)

    def login(self, username):
        client = self.app.test_client()
        login = client.get("/login")
        self.assertEqual(login.status_code, 200)
        result = self.post(
            client, "/login", username=username, password="campus-demo"
        )
        self.assertEqual(result.status_code, 200)
        return client

    def test_catalog_visibility_and_filters(self) -> None:
        guest = self.app.test_client()
        catalog = guest.get("/")
        self.assertIn("校园草坪音乐会", catalog.text)
        self.assertIn("当人工智能遇见科学", catalog.text)
        self.assertNotIn("校园摄影分享会", catalog.text)
        self.assertEqual(guest.get("/events/4").status_code, 404)
        result = guest.get("/", query_string={"q": "羊山湖", "kind": "运动健康"})
        self.assertIn("校园环湖晨跑计划", result.text)
        self.assertNotIn("校园草坪音乐会", result.text)
        self.assertIn("找到 1 项活动", result.text)
        empty = guest.get("/", query_string={"q": "不存在的活动"})
        self.assertIn("找到 0 项活动", empty.text)
        self.assertIn("没有找到公开活动", empty.text)
        self.assertNotIn("项活动开放报名", empty.text)

    def test_login_preserves_chosen_session_through_account_and_retry(self) -> None:
        client = self.app.test_client()
        event = client.get("/events/2?session=3")
        login_link = re.search(r'href="([^"]+)">登录报名</a>', event.text)
        self.assertIsNotNone(login_link)
        login = client.get(unescape(login_link.group(1)))
        account_link = re.search(r'href="([^"]+)">参与者</a>', login.text)
        self.assertIsNotNone(account_link)
        selected_account = client.get(unescape(account_link.group(1)))
        fields = dict(re.findall(
            r'<input type="hidden" name="([^"]+)" value="([^"]*)">',
            selected_account.text,
        ))
        self.assertEqual(fields["session"], "3")
        fields.update(username="student", password="wrong-password")
        failure = self.post(client, "/login", **fields)
        self.assertEqual(failure.status_code, 401)
        self.assertIn('name="session" value="3"', failure.text)

        fields["password"] = "campus-demo"
        result = self.post(client, "/login", **fields)
        self.assertEqual(result.status_code, 200)
        chosen = re.search(r'name="session" value="([^"]+)"', result.text)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen.group(1), "3")
        application = self.post(
            client, "/events/2/register", session=chosen.group(1),
            category="3", name="参加者甲", contact="lab@example.com",
        )
        self.assertIn("报名成功", application.text)
        self.assertIn("讨论场", application.text)
        self.assertNotIn("主题讲座", application.text)

    def test_approval_updates_catalog_and_csrf_is_required(self) -> None:
        organizer = self.login("organizer")
        starts = datetime.now(CAMPUS_TIME) + timedelta(days=3)
        deadline = starts - timedelta(hours=1)
        fields = {
            "name": "校内安全演练讲座", "kind": "学术讲座", "description": "讨论活动管理",
            "eligibility": "", "session_key": "1", "s1_name": "交流场",
            "s1_location": "校园报告厅", "s1_capacity": "12",
            "s1_starts_at": starts.replace(tzinfo=None).isoformat(timespec="minutes"),
            "s1_registration_deadline": deadline.replace(tzinfo=None).isoformat(timespec="minutes"),
            "s1_category": "普通", "s1_price": "3.50",
        }
        response = self.post(organizer, "/organizer/new", **fields)
        self.assertEqual(response.status_code, 200)
        self.assertIn("活动草稿已保存", response.text)
        self.assertEqual(organizer.post("/organizer/5/submit").status_code, 400)
        self.assertIn("活动已提交审核", self.post(organizer, "/organizer/5/submit").text)
        self.assertNotIn("校内安全演练讲座", organizer.get("/").text)
        self.assertEqual(organizer.get("/review").status_code, 403)

        admin = self.login("admin")
        self.assertIn("校内安全演练讲座", admin.get("/review?event=5").text)
        response = self.post(admin, "/review/5/approve")
        self.assertIn("活动已发布", response.text)
        self.assertIn("校内安全演练讲座", admin.get("/").text)
        self.assertIn("¥3.50", admin.get("/events/5").text)

    @unittest.skipUnless(QR_AVAILABLE, "网页扫码需要安装二维码依赖")
    def test_waitlist_ticket_checkin_and_roster_export(self) -> None:
        first = self.login("student")
        second = self.login("student2")
        application = {"session": "2", "category": "2", "contact": "lab@example.com"}
        self.assertIn(
            "报名成功",
            self.post(first, "/events/2/register", name="参加者甲", **application).text,
        )
        self.assertIn(
            "已加入候补",
            self.post(second, "/events/2/register", name="参加者乙", waitlist="on", **application).text,
        )
        self.assertEqual(second.get("/tickets/1/qr.png").status_code, 404)
        self.assertIn("已取消", self.post(first, "/my/1/cancel").text)
        image = second.get("/tickets/2/qr.png")
        self.assertEqual(image.mimetype, "image/png")
        self.assertTrue(image.data.startswith(b"\x89PNG"))
        self.assertEqual(first.get("/tickets/1/qr.png").status_code, 404)

        checker = self.login("checker")
        for expected in ("签到成功", "首次签到时间"):
            response = self.post(
                checker, "/check-in", session="2",
                qr=(BytesIO(image.data), "ticket.png"),
            )
            self.assertIn(expected, response.text)
        self.assertIn("已签到", second.get("/my").text)

        organizer = self.login("organizer")
        self.assertIn("参加者乙", organizer.get("/rosters?session=2").text)
        roster = self.post(organizer, "/rosters/2/export", status="checked-in")
        records = list(csv.DictReader(StringIO(roster.data.decode("utf-8-sig"))))
        self.assertEqual([record["姓名"] for record in records], ["参加者乙"])
        self.assertTrue(records[0]["签到时间"])
        admin = self.login("admin")
        self.assertIn("导出名单", admin.get("/audit?action=roster.export").text)
