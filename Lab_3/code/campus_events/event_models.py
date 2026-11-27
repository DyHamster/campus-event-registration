"""活动、场次和报名类别的业务数据。"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

CAMPUS_TIME = timezone(timedelta(hours=8))


class EventStatus(str, Enum):
    """活动从创建到取消的状态。"""

    DRAFT = "draft"
    PENDING = "pending"
    REJECTED = "rejected"
    PUBLISHED = "published"
    CANCELLED = "cancelled"


class EventError(Exception):
    """活动信息无效，或当前状态不允许执行操作。"""


@dataclass(frozen=True, slots=True)
class RegistrationCategory:
    """单个场次下的报名类别，金额以分保存。"""

    name: str
    price_cents: int
    id: int | None = None


@dataclass(frozen=True, slots=True)
class Session:
    """有单独容量、地点和报名截止时间的活动场次。"""

    name: str
    starts_at: datetime
    location: str
    capacity: int
    registration_deadline: datetime
    categories: tuple[RegistrationCategory, ...]
    id: int | None = None
    confirmed_count: int = 0


@dataclass(frozen=True, slots=True)
class EventDraft:
    """举办方输入的活动内容。"""

    name: str
    kind: str
    description: str
    eligibility: str
    sessions: tuple[Session, ...]


@dataclass(frozen=True, slots=True)
class Event:
    """数据库中一项活动的基本信息及状态。"""

    id: int
    organizer_id: int
    name: str
    kind: str
    description: str
    eligibility: str
    status: EventStatus
    review_note: str


@dataclass(frozen=True, slots=True)
class EventDetail:
    """活动详情及所属场次。"""

    event: Event
    sessions: tuple[Session, ...]
