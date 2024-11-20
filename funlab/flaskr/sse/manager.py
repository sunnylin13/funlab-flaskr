import logging
import queue
import threading
from datetime import datetime, timedelta, timezone
import uuid
from funlab.core.dbmgr import DbMgr
from funlab.utils import log
from sqlalchemy import select

from .models import EventBase, EventEntity, EventPriority
import queue
import threading
import time
from collections import defaultdict
from typing import Dict
class ConnectionManager:
    def __init__(self, max_connections_per_user: int):
        self.max_connections = max_connections_per_user
        self.user_connections: Dict[int, Dict[str, queue.Queue]] = defaultdict(dict)
        self.users_connect_time: Dict[str, float] = {}
        self._lock = threading.Lock()

    def _generate_stream_id(self) -> str:
        return str(uuid.uuid4())

    def add_connection(self, user_id: int, stream: queue.Queue) -> str:
        with self._lock:
            if len(self.user_connections[user_id]) >= self.max_connections:
                # Remove oldest connection
                oldest_stream_id = min(
                    self.user_connections[user_id],
                    key=lambda sid: self.users_connect_time.get(sid, 0)
                )
                self.remove_connection(user_id, oldest_stream_id)

            stream_id = self._generate_stream_id()
            self.user_connections[user_id][stream_id] = stream
            self.users_connect_time[stream_id] = time.time()
            return stream_id

    def remove_connection(self, user_id: int, stream_id: str):
        with self._lock:
            if stream_id in self.user_connections[user_id]:
                del self.user_connections[user_id][stream_id]
                self.users_connect_time.pop(stream_id, None)

            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

    def get_user_streams(self, user_id: int) -> set[queue.Queue]: # Dict[str, queue.Queue]:
        return set(self.user_connections.get(user_id, {}).values())

    def get_all_streams(self) -> set[queue.Queue]:
        all_streams = set()
        for streams in self.user_connections.values():
            all_streams.update(streams.values())
        return all_streams

class EventManager:
    _event_classes: Dict[str, type[EventBase]] = {}

    def __init__(self, dbmgr:DbMgr, max_event_queue_size=1000, max_events_per_stream=100):
        self.mylogger = log.get_logger(self.__class__.__name__, level=logging.INFO)
        self.dbmgr:DbMgr = dbmgr
        self.connection_manager = ConnectionManager(max_connections_per_user=10)
        # todo: check if needed
        # self.metrics = Metrics()
        self.event_queue: queue.Queue = queue.Queue(maxsize=max_event_queue_size)
        self.max_events_per_stream = max_events_per_stream
        self.lock = threading.Lock()
        self.is_shutting_down = False
        self._recover_stored_events()
        self.distributor_thread = self.start_event_distributor()

    @classmethod
    def register_event(cls, event_class: type[EventBase]): # , payload_class: type[PayloadBase]):
        event_type = event_class.__name__.removesuffix('Event')
        cls._event_classes[event_type] = event_class

    def create_event(self, event_type: str,
                    target_userid: int,
                    priority: EventPriority = EventPriority.NORMAL, expire_after: int = None,  # minutes
                    **payload_kwargs) -> EventBase:
        if not(event_class:= self._event_classes.get(event_type, None)):
            raise ValueError(f"Not register event class for event type: {event_type}")
        expired_at = datetime.now(timezone.utc) + timedelta(minutes=expire_after) if expire_after else None
        event = event_class(target_userid=target_userid, priority=priority, expired_at=expired_at,
                           **payload_kwargs)
        # Store in database
        self._store_event(event)
        try:
            self._put_event(event)
        except queue.Full:
            self.mylogger.error(f"Event queue is full! Event {event} is dropped!")
            event = None
        return event

    def _put_event(self, event: EventBase):
        with self.lock:
            self.event_queue.put(event)

    def _store_event(self, event: EventBase):
        with self.dbmgr.session_context() as session:
            if event_entity:=event.to_entity():
                session.add(event_entity)
                session.commit()
                event.id = event_entity.id

    def set_event_read(self, event: EventBase):
        event.is_read = True
        with self.dbmgr.session_context() as session:
            if event_entity:= session.query(EventEntity).filter_by(id=event.id).one_or_none():
                event_entity.is_read = True

                # remove global event concept
                # if event.is_global() and \
                #     not any(read_user.user_id == read_user_id for read_user in event_entity.read_users):
                #         event_entity.read_users.append(ReadUsersEntity(user_id=read_user_id))
                # else:
                # if event.target_userid==read_user_id:
                #     # self._remove_event_from_queue(event)
                #     event.is_read = True
                #     session.delete(event_entity)
                # else:
                #     self.mylogger.error(f"set_event_read for Event {event.id} target_user:{event.target_userid} is not for user {read_user_id}")

    def _recover_stored_events(self):
        with self.dbmgr.session_context() as session:
            stmt = select(EventEntity).order_by(EventEntity.priority.desc(), EventEntity.created_at.asc())  # .where(EventEntity.is_expired == False)
            unprocessed_events: list[EventEntity] = session.execute(stmt).scalars().all()
            for event_entity in unprocessed_events:
                try:
                    if event_entity.is_expired or event_entity.is_read:
                        session.delete(event_entity)
                        continue
                    event_class = self._event_classes[event_entity.event_type]
                    event = event_class.from_entity(event_entity)
                    self._put_event(event)
                except queue.Full:
                    break

    def _distribute_event(self, event: EventBase):
        # remove global event concept, if need to be global, send to all
        # if event.is_global:
        #     streams = self.connection_manager.get_all_streams()
        # else:
        #     streams = self.connection_manager.get_user_streams(event.target_userid)
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
                        if event.is_read or event.is_expired:
                            continue
                        self._distribute_event(event)
                except queue.Empty:
                    continue
                except Exception as e:
                    self.mylogger.error(f"Event distribution error: {e}")

        distributor_thread = threading.Thread(target=distributor, daemon=True)
        distributor_thread.start()
        return distributor_thread

    def register_user_stream(self, user_id: int) -> queue.Queue[EventBase]:
        stream = queue.Queue(maxsize=self.max_events_per_stream)
        if stream_id:=self.connection_manager.add_connection(user_id, stream):
            return stream_id
        return None

    def unregister_user_stream(self, user_id: int, stream_id: str):
        self.connection_manager.remove_connection(user_id, stream_id)


