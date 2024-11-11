import logging
import queue
import threading
import json
import signal
import atexit
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Set
from flask import Flask
from funlab.core.dbmgr import DbMgr
from funlab.flaskr.app import FunlabFlask
from funlab.flaskr.sse.utils import Metrics
from funlab.utils import log
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, scoped_session, sessionmaker
from contextlib import contextmanager

from .models import EventBase, EventEntity, EventPriority, PayloadBase
import queue
import threading
import time
from collections import defaultdict
from typing import Dict, Set

class ConnectionManager:
    def __init__(self, max_connections_per_user: int):
        self.max_connections = max_connections_per_user
        self.user_connections: Dict[int, Set[queue.Queue]] = defaultdict(set)
        self.connection_times: Dict[int, float] = {}
        self._lock = threading.Lock()

    def add_connection(self, user_id: int, stream: queue.Queue) -> bool:
        with self._lock:
            if len(self.user_connections[user_id]) >= self.max_connections:
                # Remove oldest connection
                oldest_stream = min(
                    self.user_connections[user_id],
                    key=lambda s: self.connection_times.get(id(s), 0)
                )
                self.remove_connection(user_id, oldest_stream)

            self.user_connections[user_id].add(stream)
            self.connection_times[id(stream)] = time.time()
            return True

    def remove_connection(self, user_id: int, stream: queue.Queue):
        with self._lock:
            if stream in self.user_connections[user_id]:
                self.user_connections[user_id].remove(stream)
                self.connection_times.pop(id(stream), None)

            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

    def get_user_streams(self, user_id: int) -> Set[queue.Queue]:
        return self.user_connections.get(user_id, set())

    def get_all_streams(self) -> Set[queue.Queue]:
        all_streams = set()
        for streams in self.user_connections.values():
            all_streams.update(streams)
        return all_streams

class EventManager:
    _event_classes: dict[str, type[EventBase]] = {}

    def __init__(self, dbmgr:DbMgr, max_queue_size=1000, max_client_events=100):
        self.mylogger = log.get_logger(self.__class__.__name__, level=logging.INFO)
        self.dbmgr:DbMgr = dbmgr
        self.connection_manager = ConnectionManager(dbmgr)
        self.metrics = Metrics()
        self.global_event_queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self.user_event_queues: dict[int, queue.Queue] = {}
        self.active_user_streams: dict[int, Set[queue.Queue]] = {}
        self.max_client_events = max_client_events
        self.lock = threading.Lock()
        self.is_shutting_down = False
        self._recover_stored_events()
        self.distributor_thread = self.start_event_distributor()

    @classmethod
    def register_event(cls, event_type: str, event_class: type[EventBase]):
        cls._event_classes[event_type] = event_class

    @property
    def all_event_queues(self)->list[queue.Queue]:
        return list(self.user_event_queues.values()).insert(0, self.global_event_queue)

    def create_event(self, event_type: str, payload: PayloadBase,
                    target_userid: Optional[int] = None,
                    priority: EventPriority = EventPriority.NORMAL,
                    is_read: bool = False,
                    created_at: datetime = datetime.now(timezone.utc), expires_at: datetime = None,
                    **kwargs) -> EventBase:
        if event_type not in self._event_classes:
            raise ValueError(f"Unknown event type: {event_type}")
        event_class = self._event_classes[event_type]
        event: EventBase = event_class(event_type=event_type, payload=payload,
                           target_userid=target_userid, priority=priority, is_read=is_read, created_at=created_at, expires_at=expires_at,
                           **kwargs)
        # Store in database
        self._store_event(event)
        # Add to queue
        try:
            self._put_event(event)
        except queue.Full:
            if event.is_global():
                self.mylogger.error("Global event queue is full")
            else:
                self.mylogger.error(f"User id={event.target_userid} event queue is full")
            raise RuntimeError("Event system is overloaded")
        
    def _put_event(self, event: EventBase):
        if event.is_global():
            self.global_event_queue.put_nowait(event)
        else:
            self.user_event_queues[event.get('user_id')].put_nowait(event)

    def _store_event(self, event: EventBase):
        with self.dbmgr.session_context() as session:
            session.add(event.to_entity())

    def _recover_stored_events(self):
        with self.dbmgr.session_context() as session:
            stmt = select(EventEntity).order_by(EventEntity.created_at.asc())  # .where(EventEntity.is_expired == False)
            unprocessed_events: list[EventEntity] = session.execute(stmt).scalars().all()
            for event_entity in unprocessed_events:
                try:
                    event_class = self._event_classes[event_entity.event_type]
                    event = event_class().from_entity(event_entity)
                    if event.is_expired:
                        session.delete(event_entity)
                        continue
                    self._put_event(event)
                except queue.Full:
                    break
            session.commit()

    def _distribute_global_event(self, event: EventBase):
        with self.lock:
            for user_streams in self.active_user_streams.values():
                for stream in user_streams:
                    try:
                        if stream.qsize() < self.max_client_events:
                            stream.put_nowait(event)
                    except queue.Full:
                        stream.get_nowait()
                        stream.put_nowait(event)

    def _distribute_user_event(self, event: EventBase):
        user_id = event.get('user_id')
        if user_id is None:
            return

        with self.lock:
            if user_id in self.active_user_streams:
                for stream in self.active_user_streams[user_id]:
                    try:
                        if stream.qsize() < self.max_client_events:
                            stream.put_nowait(event)
                    except queue.Full:
                        stream.get_nowait()
                        stream.put_nowait(event)

    def shutdown(self):
        if self.is_shutting_down:
            return
        self.is_shutting_down = True
        self.mylogger.info("Shutting down event notification manager...")
        for queue in self.all_event_queues:
            while not queue.empty():
                try:
                    event = queue.get_nowait()
                    self._store_event(event)
                except queue.Empty:
                    break
        self.mylogger.info("All unprocessed events have been saved")

    def start_event_distributor(self):
        def distributor():
            while not self.is_shutting_down:
                try:
                    for queue in self.all_event_queues:
                        while not queue.empty():
                            event: EventBase = queue.get(timeout=1)
                            if event.is_global():
                                self._distribute_global_event(event)
                            else:
                                self._distribute_user_event(event)
                except queue.Empty:
                    continue
                except Exception as e:
                    self.mylogger.error(f"Event distribution error: {e}")

        distributor_thread = threading.Thread(target=distributor, daemon=True)
        distributor_thread.start()
        return distributor_thread

    def register_user_stream(self, user_id: int) -> queue.Queue:
        with self.lock:
            user_stream = queue.Queue(maxsize=self.max_client_events)
            if user_id not in self.active_user_streams:
                self.active_user_streams[user_id] = set()
            self.active_user_streams[user_id].add(user_stream)
            return user_stream

    def unregister_user_stream(self, user_id: int, stream: queue.Queue):
        with self.lock:
            if user_id in self.active_user_streams:
                self.active_user_streams[user_id].discard(stream)
                if not self.active_user_streams[user_id]:
                    del self.active_user_streams[user_id]


