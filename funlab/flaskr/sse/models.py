"""
SSE event models for funlab-flaskr.

When the funlab-sse plugin is installed this module re-exports its canonical
definitions to avoid registering the same SQLAlchemy table twice in
APP_ENTITIES_REGISTRY.  When the plugin is absent the models are defined here
as a self-contained fallback.
"""

# -- Try plugin-provided models first -----------------------------------------
try:
    from funlab.sse.model import (  # noqa: F401
        PayloadBase,
        EventPriority,
        EventBase,
        EventEntity,
        SystemNotificationPayload,
        SystemNotificationEvent,
    )
    _SSE_MODELS_FROM_PLUGIN = True
except (ImportError, AttributeError):
    _SSE_MODELS_FROM_PLUGIN = False

if not _SSE_MODELS_FROM_PLUGIN:
    # -- Fallback: define inline (funlab-sse not installed) -------------------
    import json
    from dataclasses import dataclass, field
    from datetime import datetime, timezone
    from enum import Enum

    from funlab.core import _Readable
    from funlab.core.appbase import APP_ENTITIES_REGISTRY as entities_registry
    from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String
    from sqlalchemy import Enum as SQLEnum
    from sqlalchemy.ext.hybrid import hybrid_property
    from tzlocal import get_localzone

    @dataclass
    class PayloadBase:
        @classmethod
        def from_jsonstr(cls, payload_str: str) -> 'PayloadBase':
            data = json.loads(payload_str)
            return cls(**data)

        def to_json(self) -> str:
            return json.dumps(self.__dict__)

        def __str__(self) -> str:
            return self.to_json()

    class EventPriority(Enum):
        LOW = 0
        NORMAL = 1
        HIGH = 2
        CRITICAL = 3

    @dataclass
    class EventBase(_Readable):
        """In-memory representation of a single, user-targeted SSE event."""

        id: int = field(init=False)
        event_type: str = field(init=False)
        payload: PayloadBase = field(init=False)
        target_userid: int
        priority: EventPriority = EventPriority.NORMAL
        is_read: bool = field(init=False, default=False)
        is_recovered: bool = field(init=False, default=False)
        created_at: datetime = field(init=False, default_factory=lambda: datetime.now(timezone.utc))
        expired_at: datetime = None

        def __init__(self, target_userid: int = None,
                     priority: EventPriority = EventPriority.NORMAL,
                     expired_at: datetime = None,
                     payload: PayloadBase = None,
                     **payload_kwargs):
            self.id = None
            self.event_type = self.__class__.__name__.removesuffix('Event')
            self.payload = payload if payload else self.__annotations__['payload'](**payload_kwargs)
            self.target_userid = target_userid
            self.priority = priority
            self.is_read = False
            self.is_recovered = False
            self.created_at = datetime.now(timezone.utc)
            self.expired_at = expired_at

        @property
        def is_expired(self) -> bool:
            return bool(self.expired_at and datetime.now(timezone.utc) > self.expired_at)

        @property
        def local_created_at(self) -> datetime:
            return self.created_at.astimezone(get_localzone())

        @property
        def local_expires_at(self):
            return self.expired_at.astimezone(get_localzone()) if self.expired_at else None

        def to_json(self) -> str:
            return super().to_json()

        def to_dict(self) -> dict:
            """Serialise to a dict for JSON-encoding and sending to the browser."""
            return {
                "id": self.id,
                "event_type": self.event_type,
                "priority": self.priority.name,
                "created_at": self.created_at.isoformat(),
                "payload": self.payload.__dict__ if self.payload else {},
                "is_recovered": self.is_recovered,
            }

        def to_entity(self):
            """Convert to EventEntity for DB persistence. Returns None if already read/expired."""
            if self.is_read or self.is_expired:
                return None
            entity = EventEntity(
                event_type=self.event_type,
                payload=self.payload.to_json(),
                target_userid=self.target_userid,
                priority=self.priority,
                expired_at=self.expired_at,
            )
            entity.is_read = self.is_read
            entity.created_at = self.created_at
            return entity

        @classmethod
        def from_entity(cls, entity: 'EventEntity'):
            """Reconstruct an in-memory event from a DB row. Returns None if read/expired."""
            if entity.is_read or entity.is_expired:
                return None
            payload_cls = cls.__annotations__['payload']
            payload_obj = (
                payload_cls.from_jsonstr(entity.payload)
                if isinstance(entity.payload, str)
                else entity.payload
            )
            event = cls(
                target_userid=entity.target_userid,
                priority=entity.priority,
                expired_at=entity.expired_at,
                payload=payload_obj,
            )
            event.id = entity.id
            event.is_read = entity.is_read
            event.created_at = entity.created_at
            return event

        def sse_format(self) -> str:
            """Legacy SSE wire format. Deprecated -- prefer to_dict()."""
            return f"event: {self.event_type}\ndata: {self.payload.to_json()}\n\n"

    @entities_registry.mapped
    @dataclass
    class EventEntity(EventBase):
        """SQLAlchemy-mapped DB entity for the 'event' table."""

        __tablename__ = 'event'
        __sa_dataclass_metadata_key__ = 'sa'

        id: int = field(
            init=False,
            metadata={'sa': Column(Integer, primary_key=True, autoincrement=True)},
        )
        event_type: str = field(
            metadata={'sa': Column(String(50), nullable=False)},
        )
        payload: PayloadBase = field(
            metadata={'sa': Column(JSON, nullable=False)},
        )
        target_userid: int = field(
            default=None,
            metadata={'sa': Column(Integer, ForeignKey('user.id'), nullable=True)},
        )
        priority: EventPriority = field(
            default=None,
            metadata={'sa': Column(SQLEnum(EventPriority), default=EventPriority.NORMAL, nullable=False)},
        )
        is_read: bool = field(
            init=False,
            default=False,
            metadata={'sa': Column(Boolean, nullable=False, default=False)},
        )
        created_at: datetime = field(
            default_factory=lambda: datetime.now(timezone.utc),
            metadata={'sa': Column(DateTime(timezone=True), nullable=False)},
        )
        expired_at: datetime = field(
            default=None,
            metadata={'sa': Column(DateTime(timezone=True), nullable=True)},
        )

        @hybrid_property
        def is_expired(self) -> bool:
            return bool(self.expired_at and datetime.now(timezone.utc) > self.expired_at)

    @dataclass
    class SystemNotificationPayload(PayloadBase):
        title: str
        message: str

    @dataclass(init=False)
    class SystemNotificationEvent(EventBase):
        """Standard in-app notification (SSE event type: SystemNotification)."""
        payload: SystemNotificationPayload
