from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine


@dataclass(frozen=True)
class Event:
    name: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


EventHandler = Callable[[Event], Coroutine[Any, Any, None] | None]


class AsyncEventBus:
    """Async Pub/Sub Event Bus — Enterprise 2026 Agent Control Plane.

    Decouples communication between WebSocket servers, Orchestrator swarms,
    Model Harness engines, and Voice Runtimes.
    """

    def __init__(self):
        self._subscribers: dict[str, list[EventHandler]] = {}
        self._lock = asyncio.Lock()
        self._event_history: list[Event] = []

    async def subscribe(self, event_name: str, handler: EventHandler) -> None:
        """Subscribes an async or sync handler function to an event topic."""
        async with self._lock:
            if event_name not in self._subscribers:
                self._subscribers[event_name] = []
            if handler not in self._subscribers[event_name]:
                self._subscribers[event_name].append(handler)

    async def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        """Unsubscribes a handler function from an event topic."""
        async with self._lock:
            if event_name in self._subscribers and handler in self._subscribers[event_name]:
                self._subscribers[event_name].remove(handler)

    async def publish(self, name: str, data: dict[str, Any] | None = None) -> Event:
        """Publishes an event to all subscribed handlers concurrently."""
        event = Event(name=name, data=dict(data or {}))

        async with self._lock:
            if len(self._event_history) >= 500:
                self._event_history.pop(0)
            self._event_history.append(event)
            handlers = list(self._subscribers.get(name, [])) + list(self._subscribers.get("*", []))

        tasks = []
        for handler in handlers:
            try:
                res = handler(event)
                if asyncio.iscoroutine(res):
                    tasks.append(res)
            except Exception:
                pass

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        return event

    def history(self, limit: int = 50) -> tuple[Event, ...]:
        """Returns recent event history for telemetry and debugging."""
        return tuple(self._event_history[-limit:])


# Global EventBus Singleton for application-wide decoupling
_global_event_bus = AsyncEventBus()


def get_event_bus() -> AsyncEventBus:
    return _global_event_bus


__all__ = ["Event", "EventHandler", "AsyncEventBus", "get_event_bus"]
