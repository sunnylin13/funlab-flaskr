import logging
import queue
import threading
from datetime import datetime, timezone
from typing import Optional, Set
from flask import Flask
from funlab.core.dbmgr import DbMgr
from funlab.flaskr.sse.utils import Metrics
from funlab.utils import log
from sqlalchemy import select

from .models import EventBase, EventEntity, EventPriority, PayloadBase, ReadUsersEntity
import queue
import threading
import time
from collections import defaultdict
from typing import Dict, Set

class ConnectionManager:
    def __init__(self, max_connections_per_user: int):
        self.max_connections = max_connections_per_user
        self.user_connections: Dict[int, Set[queue.Queue]] = defaultdict(set)
        self.users_connect_time: Dict[int, float] = {}
        self._lock = threading.Lock()

    def add_connection(self, user_id: int, stream: queue.Queue) -> bool:
        with self._lock:
            if len(self.user_connections[user_id]) >= self.max_connections:
                # Remove oldest connection
                oldest_connection = min(
                    self.user_connections[user_id],
                    key=lambda s: self.users_connect_time.get(id(s), 0)
                )
                self.remove_connection(user_id, oldest_connection)

            self.user_connections[user_id].add(stream)
            self.users_connect_time[id(stream)] = time.time()
            return True

    def remove_connection(self, user_id: int, stream: queue.Queue):
        with self._lock:
            if stream in self.user_connections[user_id]:
                self.user_connections[user_id].remove(stream)
                self.users_connect_time.pop(id(stream), None)

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
    _event_classes: Dict[str, type[EventBase]] = {}

    def __init__(self, dbmgr:DbMgr, max_event_queue_size=1000, max_events_per_stream=100):
        self.mylogger = log.get_logger(self.__class__.__name__, level=logging.INFO)
        self.dbmgr:DbMgr = dbmgr
        self.connection_manager = ConnectionManager(dbmgr)
        self.metrics = Metrics()
        self.event_queue: queue.Queue = queue.Queue(maxsize=max_event_queue_size)
        self.max_events_per_stream = max_events_per_stream
        self.lock = threading.Lock()
        self.is_shutting_down = False
        self._recover_stored_events()
        self.distributor_thread = self.start_event_distributor()

    @classmethod
    def register_event(cls, event_type: str, event_class: type[EventBase]):
        cls._event_classes[event_type] = event_class

    def create_event(self, event_type: str, payload: PayloadBase,
                    target_userid: Optional[int] = None,
                    priority: EventPriority = EventPriority.NORMAL,
                    created_at: datetime = datetime.now(timezone.utc), expires_at: datetime = None,
                    **kwargs) -> EventBase:
        if event_type not in self._event_classes:
            raise ValueError(f"Unknown event type: {event_type}")
        event_class = self._event_classes[event_type]
        event: EventBase = event_class(event_type=event_type, payload=payload,
                           target_userid=target_userid, priority=priority, created_at=created_at, expires_at=expires_at,
                           **kwargs)
        # Store in database
        self._store_event(event)
        try:
            self._put_event(event)
        except queue.Full:
            self.mylogger.error("Too much event, event queue is full???!!!")
            raise RuntimeError("Too much event, event queue is full???!!!")


    def _put_event(self, event: EventBase):
        with self.lock:
            self.event_queue.put(event)

    def _store_event(self, event: EventBase):
        with self.dbmgr.session_context() as session:
            if event_entity:=event.to_entity():
                session.add(event_entity)
                session.commit()
                event.id = event_entity.id

    def _set_event_read(self, event: EventBase, read_user_id: int):
        with self.dbmgr.session_context() as session:
            if event_entity:= session.query(EventEntity).filter_by(event_id=event.id).first():
                if event.is_global() and \
                    not any(read_user.user_id == read_user_id for read_user in event_entity.read_users):
                        event_entity.read_users.append(ReadUsersEntity(user_id=read_user_id))
                else:
                    if event.target_userid==read_user_id:
                        # self._remove_event_from_queue(event)
                        event.is_read = True
                        session.delete(event_entity)

    def _recover_stored_events(self):
        with self.dbmgr.session_context() as session:
            stmt = select(EventEntity).order_by(EventEntity.created_at.asc())  # .where(EventEntity.is_expired == False)
            unprocessed_events: list[EventEntity] = session.execute(stmt).scalars().all()
            for event_entity in unprocessed_events:
                try:
                    if event_entity.is_expired:
                        session.delete(event_entity)
                        continue
                    event_class = self._event_classes[event_entity.event_type]
                    event = event_class.from_entity(event_entity)
                    self._put_event(event)
                except queue.Full:
                    break

    def _distribute_event(self, event: EventBase):
        if event.is_global():
            streams = self.connection_manager.get_all_streams()
        else:
            streams = self.connection_manager.get_user_streams(event.target_userid)
        for stream in streams:
            try:
                if stream.qsize() < self.max_events_per_stream:
                    stream.put_nowait(event)
            except queue.Full:
                stream.get_nowait()
                stream.put_nowait(event)

    def shutdown(self):
        if self.is_shutting_down:
            return
        self.is_shutting_down = True
        self.mylogger.info("Shutting down event notification manager...")
        while not self.event_queue.empty():
            try:
                event = self.event_queue.get_nowait()
                self._store_event(event)
            except queue.Empty:
                break
        self.mylogger.info("All unprocessed events have been saved")

    def start_event_distributor(self):
        def distributor():
            while not self.is_shutting_down:
                try:
                    while not self.event_queue.empty():
                        event: EventBase = self.event_queue.get(timeout=1)
                        if not event.is_read:
                            self._distribute_event(event)
                except queue.Empty:
                    continue
                except Exception as e:
                    self.mylogger.error(f"Event distribution error: {e}")

        distributor_thread = threading.Thread(target=distributor, daemon=True)
        distributor_thread.start()
        return distributor_thread

    def register_user_stream(self, user_id: int) -> queue.Queue:
        stream = queue.Queue(maxsize=self.max_events_per_stream)
        if self.connection_manager.add_connection(user_id, stream):
            return stream
        return None

    def unregister_user_stream(self, user_id: int, stream: queue.Queue):
        self.connection_manager.remove_connection(user_id, stream)


