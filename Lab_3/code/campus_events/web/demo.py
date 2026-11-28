"""初始化界面演示活动，供独立演示数据库使用。"""

from datetime import datetime, timedelta
from pathlib import Path

from ..access import load_user
from ..check_in import CheckInService
from ..cli import initialize
from ..database import open_database
from ..event_input import parse_draft
from ..event_models import CAMPUS_TIME
from ..events import EventService


def prepare_database(path: Path, *, demo: bool) -> None:
    initialize(path, demo)
    if not demo:
        return
    with open_database(path) as connection:
        if connection.execute("SELECT 1 FROM events LIMIT 1").fetchone():
            return
        users = {
            row["username"]: load_user(connection, row["id"])
            for row in connection.execute(
                "SELECT id, username FROM users WHERE username IN ('admin', 'organizer')"
            )
        }
    for draft, published in _examples():
        with open_database(path) as connection:
            event_id = EventService(connection, users["organizer"]).create(draft)
        with open_database(path) as connection:
            EventService(connection, users["organizer"]).submit(event_id)
        if published:
            with open_database(path) as connection:
                EventService(connection, users["admin"]).approve(event_id)
            with open_database(path) as connection:
                row = connection.execute(
                    "SELECT id FROM event_sessions WHERE event_id = ? ORDER BY id LIMIT 1",
                    (event_id,),
                ).fetchone()
                CheckInService(connection, users["admin"]).grant(row["id"], "checker")


def _examples():
    now = datetime.now(CAMPUS_TIME).replace(minute=0, second=0, microsecond=0)

    def slot(name, days, hour, location, capacity, categories):
        start = (now + timedelta(days=days)).replace(hour=hour)
        deadline = start - timedelta(hours=2)
        return {
            "name": name, "starts_at": start.isoformat(), "location": location,
            "capacity": capacity, "registration_deadline": deadline.isoformat(),
            "categories": [
                {"name": kind, "price_cents": cents} for kind, cents in categories
            ],
        }

    specifications = (
        ("校园草坪音乐会", "文艺演出", "校园乐队在草坪带来一场户外演出。入场时请出示电子票。",
         [slot("草坪晚场", 3, 18, "仙林校区 · 炜华体育场", 24, [("普通入场", 0)])],
         True),
        ("当人工智能遇见科学", "学术讲座", "从校园里的研究案例出发，聊聊机器学习如何帮助科学发现。",
         [slot("主题讲座", 5, 19, "仙林校区 · 计算机楼报告厅", 1, [("旁听", 0)]),
          slot("讨论场", 6, 15, "仙林校区 · 教学楼 A202", 20, [("旁听", 0)])],
         True),
        ("校园环湖晨跑计划", "运动健康", "从羊山湖集合点出发，沿湖完成一次校园晨跑。",
         [slot("晨跑场", 6, 7, "仙林校区 · 羊山湖", 68, [("晨跑名额", 0)])],
         True),
        ("校园摄影分享会", "学术讲座", "交流校园摄影作品，并分享自然光下的拍摄方法。",
         [slot("分享场", 7, 14, "仙林校区 · 教学楼 A101", 30,
               [("旁听", 0), ("含实践材料", 1250)])], False),
    )
    for name, kind, description, sessions, published in specifications:
        yield parse_draft({
            "name": name, "kind": kind, "description": description,
            "eligibility": "校内师生", "sessions": sessions,
        }), published
