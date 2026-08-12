import asyncio
import unittest

from backend.events.bus import AsyncEventBus, Event


class TestAsyncEventBus(unittest.IsolatedAsyncioTestCase):
    async def test_publish_and_subscribe(self):
        bus = AsyncEventBus()
        received_events: list[Event] = []

        async def handler(evt: Event):
            received_events.append(evt)

        await bus.subscribe("agent.task_started", handler)
        published = await bus.publish("agent.task_started", {"task_id": "123", "profile": "RESEARCH"})

        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0].name, "agent.task_started")
        self.assertEqual(received_events[0].data["task_id"], "123")

    async def test_wildcard_subscribe(self):
        bus = AsyncEventBus()
        wildcard_events: list[Event] = []

        async def wildcard_handler(evt: Event):
            wildcard_events.append(evt)

        await bus.subscribe("*", wildcard_handler)
        await bus.publish("system.failover", {"provider": "ollama"})

        self.assertEqual(len(wildcard_events), 1)
        self.assertEqual(wildcard_events[0].name, "system.failover")


if __name__ == "__main__":
    unittest.main()
