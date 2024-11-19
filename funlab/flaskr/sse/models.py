import ast
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from funlab.core import _Readable
from pydantic import BaseModel
from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
# all of application's entity, use same registry to declarate
from funlab.core.appbase import APP_ENTITIES_REGISTRY as entities_registry
from sqlalchemy.ext.hybrid import hybrid_property
from tzlocal import get_localzone
@dataclass
class PayloadBase:
    # @classmethod
    # def from_jsonstr(cls, payload_str: str) -> 'PayloadBase':
    #     return cls.model_validate_json(payload_str)

    # def to_json(self):
    #     return self.model_dump_json()

    @classmethod
    def from_jsonstr(cls, payload_str: str) -> 'PayloadBase':
        data = json.loads(payload_str)
        return cls(**data)

    def to_json(self) -> str:
        return json.dumps(self.__dict__)

    def __str__(self):
        return self.to_json()

class EventPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3

@dataclass
class EventBase(_Readable):
    """ 單一event data class, 用於單一user事件發送, 對於相同事件內容, 但若給多個user, 非所有user, 採發送多個不同event id 的event給各user
        global event: target_userid=None, 且is_read=False, 用於發送給所有user的事件, 並且只需發送一次, 採共用event id
        is_read記錄對各別user該event是否已讀, 但在event entity則是對同一event記錄已讀user, read_users
        若是is_global要取出同event_id 的eventEntity 加入到 read_users
        若是有target_userid, 則直接儲存成為event entity, read_users只有一筆
    """
    id: int = field(init=False)  # 需在存入db後才會有id
    event_type: str = field(init=False)  # 應在各子類別中定義default值
    payload: PayloadBase = field(init=False)
    target_userid: int
    priority: EventPriority = EventPriority.NORMAL
    is_read: bool = field(init=False, default=False)  # 記錄對各別user該event是否已讀
    created_at: datetime = field(init=False, default=datetime.now(timezone.utc))
    expired_at: datetime = None

    def __init__(self, target_userid: int = None, priority: EventPriority = EventPriority.NORMAL, expired_at: datetime = None,
                 **payload_kwargs):
        self.event_type = self.__class__.__name__.removesuffix('Event')
        self.payload = self.__annotations__['payload'](**payload_kwargs)
        self.target_userid = target_userid
        self.priority = priority
        self.is_read = False
        self.created_at = datetime.now(timezone.utc)
        self.expired_at = expired_at

    # @property
    # def is_global(self):
    #     return self.target_userid is None

    @property
    def is_expired(self):
        return self.expired_at and datetime.now(timezone.utc) > self.expired_at

    @property
    def local_created_at(self):
        """Convert created_at to the local timezone for display."""
        local_tz = get_localzone()
        return self.created_at.astimezone(local_tz)

    @property
    def local_expires_at(self):
        """Convert expired_at to the local timezone for display."""
        if self.expired_at:
            local_tz = get_localzone()
            return self.expired_at.astimezone(local_tz)
        return None

    def to_json(self):
        return super().to_json()

    def to_entity(self):
        if self.is_read or self.is_expired:
            # 若event已read or expired就不需在轉成entity去儲存, raise exception避免邏輯錯誤
            # raise ValueError("Should create event entity from read or expired event object")
            return None
        entity =  EventEntity(
            event_type=self.event_type,
            payload=self.payload.to_json(),
            target_userid=self.target_userid,
            priority=self.priority,
            expired_at=self.expired_at
        )

        entity.is_read = self.is_read
        entity.created_at = self.created_at
        return entity

    @classmethod
    def from_entity(cls, entity: 'EventEntity'):
        if entity.is_read or entity.is_expired:
            # 若event entity已read or expired就不再轉成event去發送, raise exception避免邏輯錯誤
            # raise ValueError("Should create event object from read or expired EventEntity")
            return None
        event = cls(
            target_userid=entity.target_userid,
            priority=entity.priority,
            expired_at=entity.expired_at,
            **ast.literal_eval(entity.payload) if isinstance(entity.payload, str) else entity.payload.__dict__
        )
        event.id = entity.id
        event.payload = cls.__annotations__['payload'].from_jsonstr(entity.payload)
        event.is_read = entity.is_read
        event.created_at = entity.created_at
        return event

    def sse_format(self):
        """ Format the event object as a Server-Sent Event. """
        return f"event: {self.event_type}\ndata: {self.payload.to_json()}\n\n"

@entities_registry.mapped
@dataclass
class EventEntity(EventBase):
    """ SQLAlchemy Entity for EventBase

    """
    __tablename__ = 'event'
    __sa_dataclass_metadata_key__ = 'sa'

    id: int = field(init=False, metadata={'sa': Column(Integer, primary_key=True, autoincrement=True)})
    event_type: str = field(metadata={'sa': Column(String(50), nullable=False)})
    payload: PayloadBase = field(metadata={'sa': Column(JSON, nullable=False)})
    target_userid: int = field(default=None, metadata={'sa': Column(Integer, ForeignKey('user.id'), nullable=True)})
    priority: EventPriority = field(default=None, metadata={'sa': Column(SQLEnum(EventPriority), default=EventPriority.NORMAL, nullable=False)})
    is_read: bool = field(init=False, default=False, metadata={'sa': Column(Boolean, nullable=False)})  # 記錄對各別user該event是否已讀
    # if target_userid is None, it is a global event then need to keep track of read users
    # read_users: list['ReadUsersEntity'] = field(default_factory=list, metadata={'sa': relationship('ReadUsersEntity')})  # , back_populates='event'
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc), metadata={'sa': Column(DateTime(timezone=True), nullable=False)})
    expired_at: datetime = field(default=None, metadata={'sa': Column(DateTime(timezone=True), nullable=True)})

    def post_init(self):
        self.payload = self.__annotations__['payload'].from_jsonstr(self.payload) if isinstance(self.payload, str) else self.payload # Convert payload from JSON string to object

    # def is_users_read(self, user_ids: list[int]) -> bool:
    #     """應用於傳入系統所有的user_ids, 若都已讀, 則應自db中刪除此event entity"""
    #     read_user_ids = [read_user.user_id for read_user in self.read_users]
    #     if not self.is_global:
    #         return self.target_userid in read_user_ids
    #     else:
    #         return all(user_id in read_user_ids for user_id in user_ids)

    # @hybrid_property
    # def is_global(self):
    #     return self.target_userid is None

    @hybrid_property
    def is_expired(self):
        return self.expired_at and datetime.now(timezone.utc) > self.expired_at

# @entities_registry.mapped
# @dataclass
# class ReadUsersEntity:
#     __tablename__ = 'read_users'
#     __sa_dataclass_metadata_key__ = 'sa'

#     id: int = field(init=False, metadata={'sa': Column(Integer, primary_key=True, autoincrement=True)})
#     event_id: int = field(metadata={'sa': Column(Integer, ForeignKey('event.id'), nullable=False)})
#     user_id: int = field(metadata={'sa': Column(Integer, ForeignKey('user.id'), nullable=False)})
#     read_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc), metadata={'sa': Column(DateTime(timezone=True), nullable=False)})

#     # event: EventEntity = field(default=None, metadata={'sa': relationship('EventEntity', back_populates='read_users')})


@dataclass
class SystemNotificationPayload(PayloadBase):
    title: str
    message: str

@dataclass
class SystemNotificationEvent(EventBase):
    payload: SystemNotificationPayload = field(init=False)

    def __init__(self, target_userid: int = None, priority: EventPriority = EventPriority.NORMAL, expired_at: datetime = None,
                 **payload_kwargs):
        super().__init__(target_userid=target_userid, priority=priority, expired_at=expired_at, **payload_kwargs)


