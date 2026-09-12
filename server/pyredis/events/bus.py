"""Decoupled in-memory Event Bus for broadcasting internal system events."""

import asyncio
import inspect
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Union
from pyredis.events.types import Event, EventType

logger = logging.getLogger("pyredis.events")

# Handler type: either sync callable or async coroutine function
EventHandler = Union[Callable[[Event], Any], Callable[[Event], Coroutine[Any, Any, Any]]]


class EventBus:
    """Publish-subscribe bus connecting database engine, metrics, tracing, and WebSocket."""

    def __init__(self) -> None:
        self._subscribers: Dict[Union[EventType, str], List[EventHandler]] = defaultdict(list)
        self._wildcard_subscribers: List[EventHandler] = []
        self._recent_events: List[Event] = []
        self._max_recent_events: int = 500

    def subscribe(self, event_type: Union[EventType, str], handler: EventHandler) -> None:
        """Register a handler for a specific event type or wildcard '*'."""
        if event_type == "*":
            if handler not in self._wildcard_subscribers:
                self._wildcard_subscribers.append(handler)
        else:
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: Union[EventType, str], handler: EventHandler) -> None:
        """Remove a subscriber handler."""
        if event_type == "*":
            if handler in self._wildcard_subscribers:
                self._wildcard_subscribers.remove(handler)
        else:
            if handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)

    def publish(self, event: Event) -> None:
        """Publish an event to all subscribed handlers asynchronously without blocking."""
        # Store in recent history ring buffer
        self._recent_events.append(event)
        if len(self._recent_events) > self._max_recent_events:
            self._recent_events.pop(0)

        handlers = list(self._subscribers.get(event.type, [])) + list(self._wildcard_subscribers)

        for handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    asyncio.create_task(handler(event))
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Error executing event handler for {event.type}: {e}")

    def get_recent_events(
        self,
        event_type: Optional[EventType] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Retrieve recent events, optionally filtered by type."""
        events = self._recent_events
        if event_type:
            events = [e for e in events if e.type == event_type]
        return [e.to_dict() for e in reversed(events[-limit:])]

    def clear(self) -> None:
        """Clear subscribers and recent events."""
        self._subscribers.clear()
        self._wildcard_subscribers.clear()
        self._recent_events.clear()


# Global EventBus singleton
event_bus = EventBus()
