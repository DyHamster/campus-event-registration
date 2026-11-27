"""验证报名分配、候补顺序和多连接并发。"""

import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import patch

from campus_events.access import Role, User
from campus_events.database import create_schema, open_database
from campus_events.demo import seed_demo_accounts
from campus_events.event_input import read_draft
from campus_events.events import EventService
from campus_events.registrations import (
    ApplicationResult,
    Registration,
    RegistrationError,
    RegistrationService,
    RegistrationStatus,
)

EXAMPLE = (
    Path(__file__).resolve().parents[1] / "examples" / "campus-lecture.json"
)
DEADLINE = datetime.fromisoformat("2027-03-14T04:00:00+00:00")


class RegistrationWorkflowTest(unittest.TestCase):
    """准备有两个场次的已发布活动，每个场次只有一个名额。"""

    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.database = Path(directory.name) / "registrations.sqlite3"
        self.users: dict[str, User] = {}
        with open_database(self.database, create=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            create_schema(connection)
            seed_demo_accounts(connection)
            for row in connection.execute("SELECT * FROM users"):
                self.users[row["username"]] = User(
                    row["id"], row["username"], row["name"], Role(row["role"])
                )

        clock = patch(
            "campus_events.registrations.utc_now",
            return_value=DEADLINE - timedelta(seconds=1),
        )
        self.clock = clock.start()
        self.addCleanup(clock.stop)
        self.event_id = self.create_activity()
        self.publish(self.event_id)

    def create_activity(self, eligibility: str = "校内师生") -> int:
        draft = read_draft(EXAMPLE)
        sessions = tuple(replace(item, capacity=1) for item in draft.sessions)
        draft = replace(
            draft,
            eligibility=eligibility,
            sessions=sessions,
        )
        with open_database(self.database) as connection:
            organizer = EventService(connection, self.users["organizer"])
            return organizer.create(draft)

    def publish(self, event_id: int) -> None:
        with open_database(self.database) as connection:
            EventService(connection, self.users["organizer"]).submit(event_id)
        with open_database(self.database) as connection:
            EventService(connection, self.users["admin"]).approve(event_id)

    def apply(
        self,
        username: str,
        *,
        session: int = 1,
        category: int = 1,
        waitlist: bool = False,
    ) -> ApplicationResult:
        with open_database(self.database) as connection:
            service = RegistrationService(connection, self.users[username])
            return service.apply(
                session, category, name=username, contact="demo@example.com",
                join_waitlist=waitlist,
            )

    def records(self, username: str) -> tuple[Registration, ...]:
        with open_database(self.database) as connection:
            service = RegistrationService(connection, self.users[username])
            return service.list_owned()

    def cancel(self, username: str, registration: Registration) -> None:
        with open_database(self.database) as connection:
            service = RegistrationService(connection, self.users[username])
            service.cancel(registration.id)

    def test_waitlist_fifo_and_independent_sessions(self) -> None:
        first = self.apply("student").registration
        self.assertIs(first.status, RegistrationStatus.CONFIRMED)
        with self.assertRaisesRegex(RegistrationError, "名额已满"):
            self.apply("student2")
        self.assertEqual(self.records("student2"), ())

        second = self.apply("student2", category=2, waitlist=True).registration
        third = self.apply("student3", waitlist=True).registration
        self.assertEqual(
            [second.waitlist_position, third.waitlist_position], [1, 2]
        )

        same = self.apply("student", category=2, waitlist=True)
        self.assertTrue(same.existing)
        self.assertEqual(same.registration, first)
        another = self.apply("student", session=2, category=3).registration
        self.assertIs(another.status, RegistrationStatus.CONFIRMED)

        with self.assertRaisesRegex(RegistrationError, "找不到本人报名记录"):
            self.cancel("student3", first)

        self.clock.return_value = DEADLINE + timedelta(seconds=1)
        self.cancel("student", first)
        self.cancel("student", first)
        promoted = self.records("student2")[0]
        self.assertEqual(promoted.id, second.id)
        self.assertIs(promoted.status, RegistrationStatus.CONFIRMED)
        self.assertIsNone(promoted.waitlist_position)
        self.assertEqual(self.records("student3")[0].waitlist_position, 1)
        status = self.records("student")[1].status
        self.assertIs(status, RegistrationStatus.CONFIRMED)

        self.cancel("student2", second)
        status = self.records("student3")[0].status
        self.assertIs(status, RegistrationStatus.CONFIRMED)

    def test_promotion_skips_no_longer_eligible_candidate(self) -> None:
        first = self.apply("student").registration
        self.apply("student2", waitlist=True)
        self.apply("student3", waitlist=True)
        with open_database(self.database) as connection:
            connection.execute(
                "DELETE FROM campus_memberships WHERE user_id = ?",
                (self.users["student2"].id,),
            )
        self.cancel("student", first)
        candidate = self.records("student3")[0]
        self.assertIs(candidate.status, RegistrationStatus.CONFIRMED)

    def test_cancel_waitlist_does_not_release_a_confirmed_seat(self) -> None:
        self.apply("student")
        candidate = self.apply("student2", waitlist=True).registration
        self.apply("student3", waitlist=True)
        self.cancel("student2", candidate)
        still_waiting = self.records("student3")[0]
        self.assertIs(still_waiting.status, RegistrationStatus.WAITLISTED)
        self.assertEqual(still_waiting.waitlist_position, 1)
        removed = self.records("student2")[0]
        self.assertIs(removed.status, RegistrationStatus.CANCELLED)
        new = self.apply("student2", waitlist=True).registration
        self.assertGreater(new.id, removed.id)
        self.assertEqual(new.waitlist_position, 2)

    def test_concurrent_requests_compete_for_last_seat(self) -> None:
        entrants = ("student", "student2", "student", "student3")
        barrier = Barrier(len(entrants), timeout=5)

        def submit(username: str) -> ApplicationResult:
            barrier.wait()
            return self.apply(username, waitlist=True)

        with ThreadPoolExecutor(max_workers=len(entrants)) as pool:
            results = list(pool.map(submit, entrants))
        self.assertEqual(sum(item.existing for item in results), 1)
        created = sorted(
            (item.registration for item in results if not item.existing),
            key=lambda item: item.id,
        )
        self.assertEqual(len(created), 3)
        self.assertEqual(
            [record.status for record in created],
            [
                RegistrationStatus.CONFIRMED,
                RegistrationStatus.WAITLISTED,
                RegistrationStatus.WAITLISTED,
            ],
        )
        self.assertEqual(
            [record.waitlist_position for record in created], [None, 1, 2]
        )
        self.assertEqual(len(self.records("student")), 1)

    def test_eligibility_category_and_exact_cutoff(self) -> None:
        with self.assertRaisesRegex(RegistrationError, "仅接受校内师生"):
            self.apply("visitor")
        with self.assertRaisesRegex(RegistrationError, "报名类别不属于该场次"):
            self.apply("student", category=3)
        accepted = self.apply("student").registration
        self.clock.return_value = DEADLINE
        with self.assertRaisesRegex(RegistrationError, "报名已截止"):
            self.apply("student2", waitlist=True)
        self.assertEqual(self.records("student2"), ())
        self.assertEqual(self.apply("student").registration, accepted)
        self.clock.return_value = DEADLINE + timedelta(hours=2)
        with self.assertRaisesRegex(RegistrationError, "场次已开始"):
            self.cancel("student", accepted)

    def test_open_qualification_accepts_a_visitor(self) -> None:
        event_id = self.create_activity(eligibility="不限")
        self.publish(event_id)
        result = self.apply("visitor", session=3, category=4)
        self.assertIs(result.registration.status, RegistrationStatus.CONFIRMED)

    def test_event_cancel_closes_registration_without_promotion(self) -> None:
        self.apply("student")
        self.apply("student2", waitlist=True)
        with open_database(self.database) as connection:
            organizer = EventService(connection, self.users["organizer"])
            organizer.cancel(self.event_id)
        for user in ("student", "student2"):
            status = self.records(user)[0].status
            self.assertIs(status, RegistrationStatus.CANCELLED)
        with self.assertRaisesRegex(RegistrationError, "活动当前未开放报名"):
            self.apply("student3", waitlist=True)
