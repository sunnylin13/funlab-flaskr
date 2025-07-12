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
        self.eventtype_connection_users: Dict[str, set[int]] = defaultdict(set)  # event_type -> set of user_ids
        self.users_connect_time: Dict[str, float] = {}
        self._lock = threading.Lock()

    def _generate_stream_id(self) -> str:
        return str(uuid.uuid4())

    def add_connection(self, user_id: int, stream: queue.Queue, event_type:str) -> str:
        with self._lock:
            if len(self.user_connections[user_id]) >= self.max_connections:
                # Remove oldest connection
                oldest_stream_id = min(
                    self.user_connections[user_id],
                    key=lambda sid: self.users_connect_time.get(sid, 0)
                )
                self.remove_connection(user_id, oldest_stream_id, event_type)

            stream_id = self._generate_stream_id()
            self.user_connections[user_id][stream_id] = stream
            self.users_connect_time[stream_id] = time.time()
            self.eventtype_connection_users[event_type].add(user_id)
            return stream_id

    def remove_connection(self, user_id: int, stream_id: str, event_type:str):
        with self._lock:
            if stream_id in self.user_connections[user_id]:
                del self.user_connections[user_id][stream_id]
                self.users_connect_time.pop(stream_id, None)

            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
                if user_id in self.eventtype_connection_users[event_type]:
                    self.eventtype_connection_users[event_type].remove(user_id)

    def remove_all_connections(self, user_id: int):
        with self._lock:
            if user_id in self.user_connections:
                del self.user_connections[user_id]
                for event_type in self.eventtype_connection_users.keys():
                    if user_id in self.eventtype_connection_users[event_type]:
                        self.eventtype_connection_users[event_type].remove(user_id)
                # Remove all connect times for this user
                for stream_id in list(self.users_connect_time.keys()):
                    if stream_id.startswith(str(user_id)):
                        self.users_connect_time.pop(stream_id, None)

    def get_user_streams(self, user_id: int) -> set[queue.Queue]: # Dict[str, queue.Queue]:
        with self._lock:
            streams = set(self.user_connections.get(user_id, {}).values())
        return streams

    def get_all_streams(self) -> set[queue.Queue]:
        all_streams = set()
        with self._lock:
            for streams in self.user_connections.values():
                all_streams.update(streams.values())
        return all_streams

    def get_eventtype_users(self, event_type:str) -> set[int]:
        with self._lock:
            users = self.eventtype_connection_users.get(event_type, set())
        return users

class EventManager:
    _event_classes: Dict[str, type[EventBase]] = {}

    def __init__(self, dbmgr:DbMgr, max_event_queue_size=1000, max_events_per_stream=100):
        self.mylogger = log.get_logger(self.__class__.__name__, level=logging.INFO)
        self.dbmgr:DbMgr = dbmgr
        self.connection_manager = ConnectionManager(max_connections_per_user=10)
        # todo: check if needed
        # self.metrics = Metrics()
        self.event_queue: queue.Queue[EventBase] = queue.Queue(maxsize=max_event_queue_size)
        self.max_events_per_stream = max_events_per_stream
        self.lock = threading.Lock()
        self.is_shutting_down = False
        self._recover_stored_events()
        self.distributor_thread = self.start_event_distributor()
        self.cleanup_thread = self.start_event_cleanup_scheduler()

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

        # 檢查用戶是否在線，如果在線則加入事件佇列進行即時分發
        # 如果用戶不在線，事件已儲存在資料庫中，等用戶登入時會透過 _recover_user_events 恢復
        if target_userid in self.connection_manager.user_connections:
            try:
                self._put_event(event)
            except queue.Full:
                self.mylogger.error(f"Event queue is full! Event {event} is dropped!")
                event = None
        else:
            self.mylogger.debug(f"User {target_userid} not online, event {event.id} stored for later recovery")

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
        # 系統啟動時不再將所有事件加入全局佇列
        # 只清理過期和已讀的事件
        with self.dbmgr.session_context() as session:
            stmt = select(EventEntity).where(
                (EventEntity.is_expired == True) | (EventEntity.is_read == True)
            )
            expired_or_read_events: list[EventEntity] = session.execute(stmt).scalars().all()

            for event_entity in expired_or_read_events:
                session.delete(event_entity)

            if expired_or_read_events:
                session.commit()
                # self.mylogger.debug(f"Cleaned up {len(expired_or_read_events)} expired/read events on startup")

    def _recover_user_events(self, user_id: int, event_type: str):
        """恢復特定用戶的未讀事件到其 stream 中"""
        with self.dbmgr.session_context() as session:
            stmt = select(EventEntity).where(
                EventEntity.target_userid == user_id,
                EventEntity.event_type == event_type,
                EventEntity.is_read == False
            ).order_by(EventEntity.priority.desc(), EventEntity.created_at.asc())

            user_events: list[EventEntity] = session.execute(stmt).scalars().all()

            # 獲取用戶的 streams
            user_streams = self.connection_manager.get_user_streams(user_id)

            recovered_count = 0
            for event_entity in user_events:
                try:
                    if event_entity.is_expired:
                        session.delete(event_entity)
                        continue

                    event_class = self._event_classes.get(event_entity.event_type)
                    if not event_class:
                        self.mylogger.warning(f"Unknown event type: {event_entity.event_type}")
                        continue

                    event = event_class.from_entity(event_entity)
                    if event:
                        event.is_recovered = True # 標記為恢復的事件
                        recovered_count += 1
                        # 直接發送到用戶的所有 streams
                        for stream in user_streams:
                            try:
                                if stream.qsize() < self.max_events_per_stream:
                                    stream.put_nowait(event)
                                else:
                                    # 如果佇列滿了，移除最舊的事件再加入新的
                                    stream.get_nowait()
                                    stream.put_nowait(event)
                            except queue.Full:
                                pass  # 忽略無法加入的事件

                except Exception as e:
                    self.mylogger.error(f"Error recovering event {event_entity.id} for user {user_id}: {e}")

            session.commit()  # 提交刪除的過期事件

            if recovered_count > 0:
                self.mylogger.debug(f"Recovered {recovered_count} events for user {user_id}")

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

    def clean_up_events(self):
        """Batch clean up expired or read events from the database."""
        # self.mylogger.debug("Starting event cleanup...")
        with self.dbmgr.session_context() as session:
            # Query expired or read events
            stmt = select(EventEntity).where(
                EventEntity.is_read == True
                or EventEntity.expired_at <= datetime.now(timezone.utc)
            )
            events_to_delete = session.execute(stmt).scalars().all()

            # Delete events in batch
            for event_entity in events_to_delete:
                session.delete(event_entity)
            session.commit()
        # self.mylogger.degug(f"Cleaned up {len(events_to_delete)} events.")

    def start_event_cleanup_scheduler(self, interval_minutes=30):
        """Start a background thread to periodically clean up events."""
        def cleanup_scheduler():
            while not self.is_shutting_down:
                try:
                    self.clean_up_events()
                    time.sleep(interval_minutes * 60)
                except Exception as e:
                    self.mylogger.error(f"Event cleanup error: {e}")

        cleanup_thread = threading.Thread(name='event_cleanup_scheduler', target=cleanup_scheduler, daemon=True)
        cleanup_thread.start()
        return cleanup_thread

    def shutdown(self):
        """Gracefully shut down the EventManager."""
        if self.is_shutting_down:
            return
        self.is_shutting_down = True  # Signal threads to stop
        self.mylogger.info("Shutting down event notification manager...")
        # Close all active connections
        self.mylogger.info("Unregistering all user streams...")
        # Create a copy of user_ids to avoid RuntimeError during iteration
        all_user_ids = list(self.connection_manager.user_connections.keys())
        for user_id in all_user_ids:
            self.connection_manager.remove_all_connections(user_id)
        # save unprocessed events
        while not self.event_queue.empty():
            try:
                event: EventBase = self.event_queue.get_nowait()
                if not event.is_read and not event.is_expired:
                    self._store_event(event)
            except queue.Empty:
                break
        self.mylogger.info("All unprocessed events have been saved")
        # Stop distributor thread
        self.mylogger.info("Stopping event distributor thread...")
        self.distributor_thread.join(timeout=10)

        # Perform final cleanup
        self.mylogger.info("Performing final event cleanup...")
        self.clean_up_events()

        # Stop cleanup scheduler thread
        self.mylogger.info("Stopping event cleanup scheduler thread...")
        self.cleanup_thread.join(timeout=10)

        self.mylogger.info("EventManager shutdown complete.")

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

        distributor_thread = threading.Thread(name='event_distributer', target=distributor, daemon=True)
        distributor_thread.start()
        return distributor_thread

    def register_user_stream(self, user_id: int, event_type) -> queue.Queue[EventBase]:
        stream = queue.Queue(maxsize=self.max_events_per_stream)
        if stream_id:=self.connection_manager.add_connection(user_id, stream, event_type):
            # 當用戶建立連線時，恢復其未讀事件
            self._recover_user_events(user_id, event_type)
            return stream_id
        return None

    def unregister_user_stream(self, user_id: int, stream_id: str, event_type:str):
        self.connection_manager.remove_connection(user_id, stream_id, event_type)


