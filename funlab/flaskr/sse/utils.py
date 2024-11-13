from datetime import datetime
from typing import Tuple
import threading

from funlab.flaskr.sse.models import EventPriority

class EventValidator:
    @staticmethod
    def validate_event(event_data: dict) -> Tuple[bool, str]:
        required_fields = {'type', 'data'}
        if not all(field in event_data for field in required_fields):
            return False, f"Missing required fields: {required_fields - set(event_data.keys())}"

        if 'expires_at' in event_data:
            try:
                expires_at = datetime.fromisoformat(event_data['expires_at'])
                if expires_at < datetime.utcnow():
                    return False, "Event already expired"
            except ValueError:
                return False, "Invalid expires_at format"

        if 'priority' in event_data:
            try:
                EventPriority(event_data['priority'])
            except ValueError:
                return False, "Invalid priority value"

        return True, ""

class Metrics:
    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self):
        with self._lock:
            self.total_events = 0
            self.delivered_events = 0
            self.failed_events = 0
            self.global_events = 0
            self.user_events = 0
            self.delivery_times = []
            self.start_time = datetime.utcnow()

    # def record_event(self, event_type: str, status: EventStatus, delivery_time: Optional[float] = None):
    #     with self._lock:
    #         self.total_events += 1

    #         if status == EventStatus.DELIVERED:
    #             self.delivered_events += 1
    #         elif status == EventStatus.FAILED:
    #             self.failed_events += 1

    #         if event_type == 'global':
    #             self.global_events += 1
    #         else:
    #             self.user_events += 1

    #         if delivery_time is not None:
    #             self.delivery_times.append(delivery_time)

    def get_stats(self) -> dict:
        with self._lock:
            return {
                'total_events': self.total_events,
                'delivered_events': self.delivered_events,
                'failed_events': self.failed_events,
                'global_events': self.global_events,
                'user_events': self.user_events,
                'avg_delivery_time': (sum(self.delivery_times) / len(self.delivery_times))
                    if self.delivery_times else 0,
                'uptime': (datetime.utcnow() - self.start_time).total_seconds()
            }