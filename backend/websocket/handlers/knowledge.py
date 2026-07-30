from __future__ import annotations

from typing import Any

from backend.websocket.context import WebSocketSessionState
from backend.websocket.contracts import MessageHandler
from backend.websocket.gateway import ConnectionManager
from backend.websocket.handlers import bind_handler_methods
from backend.websocket.handlers.common import notes_from_output


KNOWLEDGE_HANDLERS = {
    "get_notes": "get_notes",
    "read_note": "read_note",
    "save_note": "save_note",
    "get_rules": "get_rules",
    "delete_rule": "delete_rule",
    "delete_architecture": "delete_architecture",
    "delete_decision": "delete_decision",
}


class KnowledgeWebSocketHandler:
    def __init__(
        self,
        agents: Any,
        database: Any,
        connections: ConnectionManager,
    ) -> None:
        self.agents = agents
        self.database = database
        self.connections = connections

    def routes(self) -> dict[str, MessageHandler]:
        return bind_handler_methods(self, KNOWLEDGE_HANDLERS)

    async def get_notes(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        notes = await self.agents.run_obsidian_list_notes()
        await self.connections.send(
            websocket,
            {
                "type": "notes_list",
                "notes": notes_from_output(notes),
            },
        )

    async def read_note(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        filename = message.get("filename")
        content = await self.agents.run_obsidian_read_note(
            filename
        )
        await self.connections.send(
            websocket,
            {
                "type": "note_content",
                "filename": filename,
                "content": content,
            },
        )

    async def save_note(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        filename = message.get("filename")
        result = await self.agents.run_obsidian_write_note(
            filename,
            message.get("content"),
        )
        notes = await self.agents.run_obsidian_list_notes()
        await self.connections.broadcast(
            {
                "type": "notes_list",
                "notes": notes_from_output(notes),
            }
        )
        await self.connections.send(
            websocket,
            {
                "type": "note_saved",
                "filename": filename,
                "result": result,
            },
        )

    async def get_rules(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        await self.connections.send(
            websocket,
            {
                "type": "rules_list",
                "rules": (
                    self.database.get_compounding_rules()
                ),
            },
        )

    async def delete_rule(
        self,
        _websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        self.database.delete_compounding_rule(
            message.get("key")
        )
        rules = self.database.get_compounding_rules()
        await self.connections.broadcast(
            {"type": "rules_list", "rules": rules}
        )
        await self.connections.broadcast(
            {"type": "rules_updated", "rules": rules}
        )

    async def delete_architecture(
        self,
        _websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        self.database.delete_architecture_memory(
            message.get("module")
        )
        architecture = (
            self.database.get_architecture_memory()
        )
        await self.connections.broadcast(
            {
                "type": "architecture_updated",
                "architecture": architecture,
            }
        )

    async def delete_decision(
        self,
        _websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        self.database.delete_engineering_decision(
            message.get("decision")
        )
        decisions = (
            self.database.get_engineering_decisions()
        )
        await self.connections.broadcast(
            {
                "type": "decisions_updated",
                "decisions": decisions,
            }
        )
