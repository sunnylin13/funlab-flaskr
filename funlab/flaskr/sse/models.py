from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from funlab.core import _Readable
from pydantic import BaseModel
from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, ForeignKey, Enum as SQLEnum
# all of application's entity, use same registry to declarate
from funlab.core.appbase import APP_ENTITIES_REGISTRY as entities_registry
from sqlalchemy.ext.hybrid import hybrid_property
from tzlocal import get_localzone

class PayloadBase(BaseModel):
    @classmethod
    def from_jsonstr(cls, payload_str: str) -> 'PayloadBase':
        return cls.model_validate_json(payload_str)

    def to_json(self):
        return self.model_dump_json()

class EventPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3

@dataclass
class EventBase(_Readable):
    event_type: str
    payload: PayloadBase
    target_userid: int = None
    priority: EventPriority = EventPriority.NORMAL
    is_read: bool = False
    created_at: datetime = datetime.now(timezone.utc)
    expires_at: datetime = None

    @property
    def is_global(self):
        return self.target_userid is None

    @property
    def is_expired(self):
        return self.expires_at and datetime.now(timezone.utc) > self.expires_at

    def to_json(self):
        return super().to_json()

    def to_entity(self):
        return EventEntity(
            event_type=self.event_type,
            payload=self.payload.to_json(),
            target_userid=self.target_userid,
            priority=self.priority,
            is_read=self.is_read,
            created_at=self.created_at,
            expires_at=self.expires_at
        )

    def make_sse(self):
        """ Format the event object as a Server-Sent Event. """
        return f"event: {self.event_type}\ndata: {self.payload.to_json()}\n\n"

@entities_registry.mapped
@dataclass
class EventEntity(EventBase):
    __tablename__ = 'event'
    __sa_dataclass_metadata_key__ = 'sa'

    id: int = field(init=False, metadata={'sa': Column(Integer, primary_key=True, autoincrement=True)})
    event_type: str = field(metadata={'sa': Column(String(50), nullable=False)})
    payload: PayloadBase = field(metadata={'sa': Column(JSON, nullable=False)})
    target_userid: int = field(default=None, metadata={'sa': Column(Integer, ForeignKey('user.id'), nullable=True)})
    priority: EventPriority = field(default=None, metadata={'sa': Column(SQLEnum(EventPriority), default=EventPriority.NORMAL, nullable=False)})
    is_read: bool = field(default=False, metadata={'sa': Column(Boolean, default=False, nullable=False)})
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc), metadata={'sa': Column(DateTime(timezone=True), nullable=False)})
    expires_at: datetime = field(default=None, metadata={'sa': Column(DateTime(timezone=True), nullable=True)})

    def post_init(self):
        self.payload = PayloadBase.from_jsonstr(self.payload)  # Convert payload from JSON string to object

    @hybrid_property
    def is_global(self):
        return self.target_userid is None

    @hybrid_property
    def is_expired(self):
        return self.expires_at and datetime.now(timezone.utc) > self.expires_at

    def to_dto(self):  # EventBase, Data transfer object
        if isinstance(self.payload, str):
            payload = PayloadBase.from_jsonstr(self.payload)
        else:
            payload = self.payload

        return EventBase(
            event_type=self.event_type,
            payload=payload,
            target_userid=self.target_userid,
            priority=self.priority,
            is_read=self.is_read,
            created_at=self.created_at,
            expires_at=self.expires_at
        )

    def to_json(self):
        return self.to_dto().to_json()

    @property
    def local_created_at(self):
        """Convert created_at to the local timezone for display."""
        local_tz = get_localzone()
        return self.created_at.astimezone(local_tz)

    @property
    def local_expires_at(self):
        """Convert expires_at to the local timezone for display."""
        if self.expires_at:
            local_tz = get_localzone()
            return self.expires_at.astimezone(local_tz)
        return None
